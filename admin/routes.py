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
from routes import send_email, create_onedrive_folder

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
    
    # Calculate this week's reports
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week = datetime(start_of_week.year, start_of_week.month, start_of_week.day)
    reports_this_week = Report.query.filter(Report.submission_date >= start_of_week).count()
    
    # Calculate missing reports (employees who haven't submitted this week)
    all_employees = User.query.filter_by(role='employee').all()
    employees_submitted = db.session.query(Report.employee_id).filter(
        Report.submission_date >= start_of_week
    ).distinct().all()
    submitted_ids = [item[0] for item in employees_submitted]
    missing_reports = sum(1 for emp in all_employees if emp.id not in submitted_ids)
    
    # Recent reports for dashboard table
    recent_reports = Report.query.order_by(desc(Report.submission_date)).limit(5).all()
    
    # Recent activity logs
    recent_activities = ActivityLog.query.order_by(desc(ActivityLog.timestamp)).limit(5).all()
    
    log_admin_activity("Viewed admin dashboard")
    
    return render_template('admin/dashboard.html', 
                          employee_count=employee_count,
                          report_count=report_count,
                          reports_this_week=reports_this_week,
                          missing_reports=missing_reports,
                          recent_reports=recent_reports,
                          recent_activities=recent_activities,
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
                email_subject = "Welcome to SBS Corp Weekly Status Report System"
                email_body = f"""
                <html>
                <body>
                    <h2>Welcome to SBS Corp Weekly Status Report System</h2>
                    <p>Hello {form.name.data},</p>
                    <p>An account has been created for you on the SBS Corp Weekly Status Report System.</p>
                    <p><strong>Your login details:</strong></p>
                    <ul>
                        <li><strong>Email:</strong> {form.email.data}</li>
                        <li><strong>Password:</strong> {form.password.data}</li>
                    </ul>
                    <p>Please login at <a href="{request.host_url}">{request.host_url}</a></p>
                    <p>You will be required to submit weekly status reports by the end of each week.</p>
                    <p>Thank you,<br>SBS Corp Admin</p>
                </body>
                </html>
                """
                send_email(form.email.data, email_subject, email_body)
                flash(f"Employee created successfully and welcome email sent to {form.email.data}", "success")
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
            
            # Optionally send email notification
            email_subject = "SBS Corp - Your Password Has Been Reset"
            email_body = f"""
            <html>
            <body>
                <h2>Password Reset Notification</h2>
                <p>Hello {employee.name},</p>
                <p>Your password for the SBS Corp Weekly Status Report System has been reset by an administrator.</p>
                <p><strong>Your new login details:</strong></p>
                <ul>
                    <li><strong>Email:</strong> {employee.email}</li>
                    <li><strong>Password:</strong> {form.password.data}</li>
                </ul>
                <p>Please login at <a href="{request.host_url}">{request.host_url}</a></p>
                <p>Thank you,<br>SBS Corp Admin</p>
            </body>
            </html>
            """
            send_email(employee.email, email_subject, email_body)
            
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
    reports = Report.query.order_by(desc(Report.submission_date)).all()
    log_admin_activity("Viewed reports list")
    return render_template('admin/reports.html', reports=reports, now=datetime.now())

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
                status_text = "approved" if report.status == 'approved' else "rejected"
                
                email_subject = f"Weekly Report {status_text.capitalize()}"
                email_body = f"""
                <html>
                <body>
                    <h2>Weekly Report {status_text.capitalize()}</h2>
                    <p>Hello {employee.name},</p>
                    <p>Your weekly report "{report.filename}" has been <strong>{status_text}</strong>.</p>
                    
                    <p><strong>Review details:</strong></p>
                    <p>Status: {status_text.capitalize()}</p>
                    
                    <p><strong>Feedback:</strong></p>
                    <p>{report.feedback if report.feedback else "No feedback provided."}</p>
                    
                    <p>Thank you,<br>SBS Corp Admin</p>
                </body>
                </html>
                """
                send_email(employee.email, email_subject, email_body)
            
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