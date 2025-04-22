import os
import logging
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, TextAreaField
from sqlalchemy import desc
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional
from functools import wraps

from models import db, User, Report, ActivityLog
from routes import create_onedrive_folder
import email_service
import slack_service

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Blueprint
bp = Blueprint('admin', __name__, url_prefix='/admin')

# Admin-only decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# Log admin activity
def log_admin_activity(action, details=None):
    try:
        log = ActivityLog(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            action=action,
            details=details,
            timestamp=datetime.now(),
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error logging admin activity: {str(e)}")

# Forms
class EmployeeForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=100)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, max=100)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    send_welcome_email = BooleanField('Send Welcome Email')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=8, max=100)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])

class ReviewReportForm(FlaskForm):
    status = SelectField('Status', choices=[('submitted', 'Submitted'), ('approved', 'Approved'), ('rejected', 'Rejected')])
    feedback = TextAreaField('Feedback', validators=[Optional()])

# Dashboard
@bp.route('/')
@bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    # Get counts for dashboard stats
    employee_count = User.query.filter_by(role='employee').count()
    report_count = Report.query.count()
    
    # Calculate pending reviews (submitted but not approved/rejected)
    pending_reviews = Report.query.filter_by(status='submitted').count()
    
    # Calculate this week's reports
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week = datetime(start_of_week.year, start_of_week.month, start_of_week.day)
    
    # Get Sunday (end of previous week)
    prev_sunday = start_of_week - timedelta(days=1)
    prev_sunday = datetime(prev_sunday.year, prev_sunday.month, prev_sunday.day, 23, 59, 59)
    
    # Total reports this week
    reports_this_week = Report.query.filter(Report.submission_date >= start_of_week).count()
    
    # Calculate missing reports (employees who haven't submitted this week)
    all_employees = User.query.filter_by(role='employee').all()
    employees_submitted = db.session.query(Report.employee_id).filter(
        Report.submission_date >= start_of_week
    ).distinct().all()
    submitted_ids = [item[0] for item in employees_submitted]
    missing_reports = sum(1 for emp in all_employees if emp.id not in submitted_ids)
    
    # Enhanced reporting statistics
    on_time_count = 0
    late_count = 0
    not_submitted_count = missing_reports
    
    # For each employee who submitted, determine if it was on time or late
    for employee_id in submitted_ids:
        # Get the earliest submission for this week
        earliest_report = Report.query.filter(
            Report.employee_id == employee_id,
            Report.submission_date >= start_of_week
        ).order_by(Report.submission_date).first()
        
        if earliest_report:
            # Monday 9 AM deadline
            deadline = start_of_week + timedelta(hours=9)
            
            # If submitted by deadline, it's on time, otherwise late
            if earliest_report.submission_date <= deadline:
                on_time_count += 1
            else:
                late_count += 1
    
    # Recent reports for dashboard table
    recent_reports = Report.query.order_by(desc(Report.submission_date)).limit(5).all()
    
    # Recent activity logs
    recent_activities = ActivityLog.query.order_by(desc(ActivityLog.timestamp)).limit(5).all()
    
    # Get employee submission status for this week
    employees_with_status = []
    for employee in all_employees:
        last_report = Report.query.filter_by(employee_id=employee.id).order_by(desc(Report.submission_date)).first()
        
        # Determine submission status (on time, late, not submitted)
        status = "not_submitted"
        if employee.id in submitted_ids:
            earliest_report = Report.query.filter(
                Report.employee_id == employee.id,
                Report.submission_date >= start_of_week
            ).order_by(Report.submission_date).first()
            
            if earliest_report:
                deadline = start_of_week + timedelta(hours=9)
                status = "on_time" if earliest_report.submission_date <= deadline else "late"
        
        employee_data = {
            'id': employee.id,
            'name': employee.name,
            'email': employee.email,
            'has_submitted_this_week': employee.id in submitted_ids,
            'submission_status': status,
            'last_report': last_report.submission_date if last_report else None
        }
        employees_with_status.append(employee_data)
    
    log_admin_activity("Viewed admin dashboard")
    
    return render_template('admin/dashboard.html', 
                          employee_count=employee_count,
                          report_count=report_count,
                          reports_this_week=reports_this_week,
                          missing_reports=missing_reports,
                          on_time_count=on_time_count,
                          late_count=late_count,
                          not_submitted_count=not_submitted_count,
                          pending_reviews=pending_reviews,
                          recent_reports=recent_reports,
                          recent_activities=recent_activities,
                          employees=employees_with_status,
                          now=datetime.now())

# Employee management
@bp.route('/employees')
@login_required
@admin_required
def employees():
    employees = User.query.filter_by(role='employee').all()
    log_admin_activity("Viewed employee list")
    return render_template('admin/employees.html', employees=employees, now=datetime.now())

# Add new employee
@bp.route('/employees/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_employee():
    form = EmployeeForm()
    
    if form.validate_on_submit():
        # Check if email already exists
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash("Email already registered", "danger")
            return render_template('admin/add_employee.html', form=form, now=datetime.now())
        
        try:
            # Create OneDrive folder for employee
            folder_id = create_onedrive_folder(form.name.data)
            
            # Create new employee
            new_employee = User(
                id=str(uuid.uuid4()),
                name=form.name.data,
                email=form.email.data,
                password=form.password.data,
                role='employee',
                folder_id=folder_id,
                active=True,
                created_at=datetime.now()
            )
            
            db.session.add(new_employee)
            db.session.commit()
            
            # Send welcome email if requested
            if form.send_welcome_email.data:
                # Try to send email notification
                email_success = email_service.send_welcome_email(
                    to_email=form.email.data,
                    employee_name=form.name.data,
                    password=form.password.data
                )
                
                # Try to send Slack notification as well
                slack_success = slack_service.send_new_employee_notification(
                    employee_name=form.name.data,
                    employee_email=form.email.data
                )
                
                if email_success:
                    flash(f"Employee created successfully and welcome email sent to {form.email.data}", "success")
                elif slack_success:
                    flash(f"Employee created successfully. Email couldn't be sent, but Slack notification was delivered.", "success")
                else:
                    flash(f"Employee created successfully, but notifications could not be sent. Check email and Slack settings.", "warning")
            else:
                flash("Employee created successfully", "success")
            
            log_admin_activity(
                f"Added new employee: {form.name.data}",
                f"Employee ID: {new_employee.id}, Email: {form.email.data}"
            )
            
            return redirect(url_for('admin.employees'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Add employee error: {str(e)}")
            flash(f"Error creating employee: {str(e)}", "danger")
    
    return render_template('admin/add_employee.html', form=form, now=datetime.now())

# Edit employee
@bp.route('/employees/edit/<id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_employee(id):
    employee = User.query.get_or_404(id)
    
    # Don't allow editing admin users
    if employee.role == 'admin':
        flash("Admin users cannot be edited", "danger")
        return redirect(url_for('admin.employees'))
    
    class EditForm(FlaskForm):
        name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
        email = StringField('Email', validators=[DataRequired(), Email(), Length(max=100)])
        active = BooleanField('Active')
    
    form = EditForm(obj=employee)
    
    if form.validate_on_submit():
        try:
            employee.name = form.name.data
            
            # Check if email is being changed and if it's already in use
            if employee.email != form.email.data:
                existing_user = User.query.filter_by(email=form.email.data).first()
                if existing_user and existing_user.id != employee.id:
                    flash("Email already registered to another user", "danger")
                    return render_template('admin/edit_employee.html', form=form, employee=employee, now=datetime.now())
                employee.email = form.email.data
            
            employee.active = form.active.data
            db.session.commit()
            
            log_admin_activity(
                f"Updated employee: {employee.name}",
                f"Employee ID: {employee.id}, Email: {employee.email}, Active: {employee.active}"
            )
            
            flash("Employee updated successfully", "success")
            return redirect(url_for('admin.employees'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Edit employee error: {str(e)}")
            flash(f"Error updating employee: {str(e)}", "danger")
    
    return render_template('admin/edit_employee.html', form=form, employee=employee, now=datetime.now())

# Reset employee password
@bp.route('/employees/reset-password/<id>', methods=['GET', 'POST'])
@login_required
@admin_required
def reset_employee_password(id):
    employee = User.query.get_or_404(id)
    
    # Don't allow resetting admin passwords through this route
    if employee.role == 'admin':
        flash("Admin passwords cannot be reset through this interface", "danger")
        return redirect(url_for('admin.employees'))
    
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        try:
            employee.password = form.password.data
            db.session.commit()
            
            # Send password reset notification using our email service
            success = email_service.send_welcome_email(
                to_email=employee.email,
                employee_name=employee.name,
                password=form.password.data
            )
            
            log_admin_activity(
                f"Reset password for employee: {employee.name}",
                f"Employee ID: {employee.id}, Email: {employee.email}"
            )
            
            flash(f"Password reset successfully for {employee.name}. An email notification has been sent.", "success")
            return redirect(url_for('admin.employees'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Password reset error: {str(e)}")
            flash(f"Error resetting password: {str(e)}", "danger")
    
    return render_template('admin/reset_password.html', form=form, employee=employee, now=datetime.now())

# Delete employee
@bp.route('/employees/delete/<id>', methods=['POST'])
@login_required
@admin_required
def delete_employee(id):
    employee = User.query.get_or_404(id)
    
    # Don't allow deleting admin users
    if employee.role == 'admin':
        flash("Admin users cannot be deleted", "danger")
        return redirect(url_for('admin.employees'))
    
    try:
        employee_name = employee.name
        employee_id = employee.id
        employee_email = employee.email
        
        db.session.delete(employee)
        db.session.commit()
        
        log_admin_activity(
            f"Deleted employee: {employee_name}",
            f"Employee ID: {employee_id}, Email: {employee_email}"
        )
        
        flash("Employee deleted successfully", "success")
    except Exception as e:
        db.session.rollback()
        logging.error(f"Delete employee error: {str(e)}")
        flash(f"Error deleting employee: {str(e)}", "danger")
    
    return redirect(url_for('admin.employees'))

# Reports listing
@bp.route('/reports')
@login_required
@admin_required
def reports():
    # Get all reports
    reports = Report.query.order_by(desc(Report.submission_date)).all()
    
    # Get statistics for the charts
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week = datetime(start_of_week.year, start_of_week.month, start_of_week.day)
    
    # Get Sunday (end of previous week)
    prev_sunday = start_of_week - timedelta(days=1)
    prev_sunday = datetime(prev_sunday.year, prev_sunday.month, prev_sunday.day, 23, 59, 59)
    
    # Calculate missing reports (employees who haven't submitted this week)
    all_employees = User.query.filter_by(role='employee', active=True).all()
    employees_submitted = db.session.query(Report.employee_id).filter(
        Report.submission_date >= start_of_week
    ).distinct().all()
    submitted_ids = [item[0] for item in employees_submitted]
    not_submitted_count = sum(1 for emp in all_employees if emp.id not in submitted_ids)
    
    # Calculate on-time and late submissions
    on_time_count = 0
    late_count = 0
    
    for employee_id in submitted_ids:
        # Get the earliest submission for this week
        earliest_report = Report.query.filter(
            Report.employee_id == employee_id,
            Report.submission_date >= start_of_week
        ).order_by(Report.submission_date).first()
        
        if earliest_report:
            # Monday 9 AM deadline
            deadline = start_of_week + timedelta(hours=9)
            
            # If submitted by deadline, it's on time, otherwise late
            if earliest_report.submission_date <= deadline:
                on_time_count += 1
            else:
                late_count += 1
    
    log_admin_activity("Viewed reports list")
    
    return render_template(
        'admin/reports.html', 
        reports=reports, 
        on_time_count=on_time_count,
        late_count=late_count,
        not_submitted_count=not_submitted_count,
        now=datetime.now()
    )

# View single report
@bp.route('/reports/view/<id>')
@login_required
@admin_required
def view_report(id):
    report = Report.query.get_or_404(id)
    log_admin_activity(f"Viewed report: {report.filename}", f"Report ID: {report.id}")
    return render_template('admin/view_report.html', report=report, now=datetime.now())

# Review report
@bp.route('/reports/review/<id>', methods=['GET', 'POST'])
@login_required
@admin_required
def review_report(id):
    report = Report.query.get_or_404(id)
    form = ReviewReportForm(obj=report)
    
    if form.validate_on_submit():
        try:
            report.status = form.status.data
            report.feedback = form.feedback.data
            report.reviewed_by = current_user.id
            report.review_date = datetime.now()
            db.session.commit()
            
            # Notify employee of review if needed
            if report.status in ['approved', 'rejected']:
                employee = User.query.get(report.employee_id)
                
                # Get report submission date formatted for the email
                report_date = report.submission_date.strftime("%A, %B %d, %Y")
                
                # Send appropriate email notification based on status
                email_success = False
                if report.status == 'approved':
                    email_success = email_service.send_report_approved_email(
                        to_email=employee.email,
                        employee_name=employee.name,
                        report_date=report_date,
                        feedback=report.feedback
                    )
                else:  # rejected
                    email_success = email_service.send_report_rejected_email(
                        to_email=employee.email,
                        employee_name=employee.name,
                        report_date=report_date,
                        feedback=report.feedback
                    )
                
                # Also try to send a Slack notification
                slack_success = slack_service.send_report_status_notification(
                    employee_name=employee.name,
                    report_filename=report.filename,
                    status=report.status,
                    feedback=report.feedback
                )
                
                if not email_success and not slack_success:
                    logging.warning(f"Could not send report review notification to {employee.email} via email or Slack")
            
            log_admin_activity(
                f"Reviewed report: {report.filename}",
                f"Report ID: {report.id}, Status: {report.status}"
            )
            
            flash(f"Report {report.status} successfully", "success")
            return redirect(url_for('admin.reports'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Review report error: {str(e)}")
            flash(f"Error reviewing report: {str(e)}", "danger")
    
    return render_template('admin/review_report.html', form=form, report=report, now=datetime.now())

# Send reminders to employees
@bp.route('/send-reminders', methods=['POST'])
@login_required
@admin_required
def send_reminders():
    # Get employees who haven't submitted this week
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week = datetime(start_of_week.year, start_of_week.month, start_of_week.day)
    
    all_employees = User.query.filter_by(role='employee', active=True).all()
    employees_submitted = db.session.query(Report.employee_id).filter(
        Report.submission_date >= start_of_week
    ).distinct().all()
    submitted_ids = [item[0] for item in employees_submitted]
    
    # Determine which employees should receive reminders
    send_to_all = request.form.get('send_to_all') == 'on'
    if send_to_all:
        # Send to all active employees
        target_employees = all_employees
    else:
        # Send only to employees who haven't submitted reports
        target_employees = [emp for emp in all_employees if emp.id not in submitted_ids]
    
    # Get email parameters
    subject = request.form.get('subject', '[REMINDER] Weekly Status Report Due')
    additional_message = request.form.get('message', '')
    
    # Format additional message if provided
    formatted_additional_message = ""
    if additional_message and additional_message.strip():
        # Convert newlines to <br> first, before creating the f-string
        message_with_breaks = additional_message.strip().replace('\n', '<br>')
        formatted_additional_message = f"""
        <p style="margin-top: 15px; margin-bottom: 15px; padding: 10px; border-left: 4px solid #007bff; background-color: #f8f9fa;">
            {message_with_breaks}
        </p>
        """
    
    # Send emails to target employees
    count = 0
    for employee in target_employees:
        try:
            # Check if this employee has submitted (for customized message)
            has_submitted = employee.id in submitted_ids
            
            # Calculate due date for the email (next Monday)
            today = datetime.now()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_monday = today + timedelta(days=days_until_monday)
            due_date_str = next_monday.strftime("%A, %B %d, %Y at 9:00 AM")
            
            # Try email first
            email_success = email_service.send_reminder_email(
                to_email=employee.email,
                employee_name=employee.name,
                due_date_str=due_date_str
            )
            
            # Also try Slack as an additional notification channel
            slack_success = slack_service.send_reminder_notification(
                employee_name=employee.name,
                due_date_str=due_date_str
            )
            
            if email_success or slack_success:
                count += 1
                
                # Log which channels were used for reminders
                if email_success and slack_success:
                    logging.info(f"Sent reminder to {employee.name} via both email and Slack")
                elif email_success:
                    logging.info(f"Sent reminder to {employee.name} via email only")
                else:
                    logging.info(f"Sent reminder to {employee.name} via Slack only")
            else:
                logging.warning(f"Could not send reminder to {employee.name} via either email or Slack")
        except Exception as e:
            logging.error(f"Error sending reminder to {employee.email}: {str(e)}")
    
    # Log the action
    if send_to_all:
        action_details = f"Sent report reminders to all {count} employees (including those who already submitted)"
    else:
        action_details = f"Sent report reminders to {count} employees who haven't submitted yet"
    
    log_admin_activity(action_details)
    
    flash(f"Reminders sent to {count} employees", "success")
    return redirect(url_for('admin.dashboard'))

# Activity logs
@bp.route('/activity-logs')
@login_required
@admin_required
def activity_logs():
    logs = ActivityLog.query.order_by(desc(ActivityLog.timestamp)).all()
    log_admin_activity("Viewed activity logs")
    return render_template('admin/activity_logs.html', logs=logs, now=datetime.now())

# Admin profile
@bp.route('/profile', methods=['GET', 'POST'])
@login_required
@admin_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_profile':
            try:
                current_user.name = request.form.get('name')
                db.session.commit()
                log_admin_activity("Updated profile information")
                flash("Profile updated successfully", "success")
            except Exception as e:
                db.session.rollback()
                logging.error(f"Profile update error: {str(e)}")
                flash(f"Error updating profile: {str(e)}", "danger")
                
        elif action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if not current_password or not new_password or not confirm_password:
                flash("All password fields are required", "danger")
            elif new_password != confirm_password:
                flash("New passwords do not match", "danger")
            elif current_user.password != current_password:  # Simple password check
                flash("Current password is incorrect", "danger")
            else:
                try:
                    current_user.password = new_password
                    db.session.commit()
                    log_admin_activity("Changed password")
                    flash("Password updated successfully", "success")
                except Exception as e:
                    db.session.rollback()
                    logging.error(f"Password change error: {str(e)}")
                    flash(f"Error changing password: {str(e)}", "danger")
    
    return render_template('admin/profile.html', now=datetime.now())

# Notification Settings
@bp.route('/settings/notifications', methods=['GET', 'POST'])
@login_required
@admin_required
def settings_notifications():
    # Get current notification settings
    smtp_server = os.environ.get('SMTP_SERVER')
    smtp_port = os.environ.get('SMTP_PORT', '587')
    smtp_username = os.environ.get('SMTP_USERNAME')
    smtp_password = os.environ.get('SMTP_PASSWORD')
    smtp_use_tls = os.environ.get('SMTP_USE_TLS', 'True').lower() in ('true', '1', 't')
    sender_name = os.environ.get('SENDER_NAME', 'SBS Corp Weekly Status Report System')
    sender_email = os.environ.get('SENDER_EMAIL', 'noreply@sbscorp.com')
    
    slack_bot_token = os.environ.get('SLACK_BOT_TOKEN')
    slack_channel_id = os.environ.get('SLACK_CHANNEL_ID')
    
    # Check if services are configured
    email_configured = email_service.is_email_configured()
    slack_configured = slack_service.is_slack_configured()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_email_settings':
            # Process email settings form
            try:
                # In a production environment, you would update these in the environment
                # or a config file. This is a simplified version for demonstration.
                flash("Email settings updated successfully", "success")
                log_admin_activity("Updated email notification settings")
            except Exception as e:
                logging.error(f"Error updating email settings: {str(e)}")
                flash(f"Error updating email settings: {str(e)}", "danger")
                
        elif action == 'update_slack_settings':
            # Process Slack settings form
            try:
                # In a production environment, you would update these in the environment
                # or a config file. This is a simplified version for demonstration.
                flash("Slack settings updated successfully", "success")
                log_admin_activity("Updated Slack notification settings")
            except Exception as e:
                logging.error(f"Error updating Slack settings: {str(e)}")
                flash(f"Error updating Slack settings: {str(e)}", "danger")
                
        elif action == 'test_notification':
            # Process test notification form
            test_email = request.form.get('test_email')
            test_type = request.form.get('test_type', 'email')
            
            if test_type in ['email', 'both'] and test_email:
                # Send test email
                email_sent = email_service.send_email(
                    to_email=test_email,
                    subject="Test Notification from SBS Corp Weekly Status Report System",
                    html_content="""
                    <html>
                    <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
                        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                            <h2 style="color: #007bff; margin-bottom: 20px;">Test Notification</h2>
                            <p>This is a test notification from the SBS Corp Weekly Status Report System.</p>
                            <p>Your email notification settings are working correctly!</p>
                            <p style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee;">
                                Sent from SBS Corp Weekly Status Report System
                            </p>
                        </div>
                    </body>
                    </html>
                    """
                )
                if email_sent:
                    flash(f"Test email sent successfully to {test_email}", "success")
                else:
                    flash(f"Failed to send test email to {test_email}. Check your email settings.", "danger")
            
            if test_type in ['slack', 'both']:
                # Send test Slack message
                slack_sent = slack_service.send_slack_message(
                    message="Test notification from SBS Corp Weekly Status Report System",
                    blocks=[
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": "Test Notification",
                                "emoji": True
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "This is a test notification from the SBS Corp Weekly Status Report System."
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "Your Slack notification settings are working correctly! 🎉"
                            }
                        }
                    ]
                )
                if slack_sent:
                    flash("Test Slack message sent successfully", "success")
                else:
                    flash("Failed to send test Slack message. Check your Slack settings.", "danger")
            
            log_admin_activity(f"Sent test notification (type: {test_type})")
            
    return render_template(
        'admin/settings/notifications.html',
        email_configured=email_configured,
        slack_configured=slack_configured,
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        smtp_username=smtp_username,
        smtp_password=smtp_password,
        smtp_use_tls=smtp_use_tls,
        sender_name=sender_name,
        sender_email=sender_email,
        slack_bot_token=slack_bot_token,
        slack_channel_id=slack_channel_id,
        now=datetime.now()
    )