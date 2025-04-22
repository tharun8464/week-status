import os
import uuid
import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Report, Notification, ActivityLog
from functools import wraps
from sqlalchemy import func, desc, asc
import secrets
from routes import send_email
import pytz

admin_bp = Blueprint('admin', __name__)

# Helper for admin-only routes
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

# Log admin activity helper
def log_admin_activity(action, details=None):
    ip = request.remote_addr
    activity = ActivityLog(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        action=action,
        details=details,
        ip_address=ip
    )
    db.session.add(activity)
    db.session.commit()

# Admin Dashboard
@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    # Get stats
    total_employees = User.query.filter_by(role='employee').count()
    total_reports = Report.query.count()
    
    # Get reports by date range (last 30 days)
    today = datetime.now().date()
    thirty_days_ago = today - timedelta(days=30)
    
    reports_by_date = db.session.query(
        func.date(Report.submission_date).label('date'),
        func.count(Report.id).label('count')
    ).filter(func.date(Report.submission_date) >= thirty_days_ago).group_by('date').all()
    
    # Format for chart
    dates = [r.date.strftime('%Y-%m-%d') for r in reports_by_date]
    counts = [r.count for r in reports_by_date]
    
    # Get recent activity
    recent_activity = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(10).all()
    
    # Get users without reports this week
    start_of_week = today - timedelta(days=today.weekday())
    missing_reports = User.query.filter_by(role='employee', active=True).outerjoin(
        Report, 
        db.and_(
            User.id == Report.employee_id,
            func.date(Report.submission_date) >= start_of_week
        )
    ).filter(Report.id == None).all()
    
    return render_template(
        'admin/dashboard.html',
        total_employees=total_employees,
        total_reports=total_reports,
        dates=dates,
        counts=counts,
        recent_activity=recent_activity,
        missing_reports=missing_reports
    )

# Employee Management
@admin_bp.route('/employees')
@login_required
@admin_required
def employees():
    employees = User.query.filter_by(role='employee').order_by(User.name).all()
    return render_template('admin/employees.html', employees=employees)

# Add Employee
@admin_bp.route('/employees/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_employee():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        
        # Validation
        if not name or not email:
            flash('Name and email are required', 'danger')
            return redirect(url_for('admin.add_employee'))
        
        # Check if email exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already exists', 'danger')
            return redirect(url_for('admin.add_employee'))
        
        # Generate reset token for password setup
        token = secrets.token_urlsafe(32)
        expires = datetime.now() + timedelta(hours=24)
        
        # Create employee without password
        from routes import create_onedrive_folder
        try:
            folder_id = create_onedrive_folder(name)
            
            new_employee = User(
                id=str(uuid.uuid4()),
                name=name,
                email=email,
                password='PENDING_SETUP',  # Will be set by user
                role='employee',
                folder_id=folder_id,
                password_reset_token=token,
                password_reset_expires=expires
            )
            
            db.session.add(new_employee)
            db.session.commit()
            
            # Send welcome email with password setup link
            setup_link = url_for('main.setup_password', token=token, _external=True)
            email_body = f'''
            <h2>Welcome to SBS Corp Weekly Status Report Portal</h2>
            <p>Dear {name},</p>
            <p>Your account has been created. Please click the link below to set up your password:</p>
            <p><a href="{setup_link}">{setup_link}</a></p>
            <p>This link will expire in 24 hours.</p>
            <p>Thank you,<br>SBS Corp Admin</p>
            '''
            
            send_email(email, 'Welcome to SBS Corp - Set Up Your Password', email_body)
            
            flash(f'Employee {name} added successfully. A password setup email has been sent.', 'success')
            log_admin_activity(f'Added employee {name}')
            return redirect(url_for('admin.employees'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding employee: {str(e)}', 'danger')
            return redirect(url_for('admin.add_employee'))
    
    return render_template('admin/add_employee.html')

# Edit Employee
@admin_bp.route('/employees/edit/<string:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_employee(id):
    employee = User.query.get_or_404(id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        active = 'active' in request.form
        
        # Validation
        if not name or not email:
            flash('Name and email are required', 'danger')
            return redirect(url_for('admin.edit_employee', id=id))
        
        # Check if email exists (excluding this user)
        existing_user = User.query.filter(User.email == email, User.id != id).first()
        if existing_user:
            flash('Email already exists', 'danger')
            return redirect(url_for('admin.edit_employee', id=id))
        
        # Update employee
        employee.name = name
        employee.email = email
        employee.active = active
        
        db.session.commit()
        
        flash(f'Employee {name} updated successfully', 'success')
        log_admin_activity(f'Updated employee {name}')
        return redirect(url_for('admin.employees'))
    
    return render_template('admin/edit_employee.html', employee=employee)

# Reset Employee Password
@admin_bp.route('/employees/reset-password/<string:id>', methods=['POST'])
@login_required
@admin_required
def reset_employee_password(id):
    employee = User.query.get_or_404(id)
    
    # Generate reset token
    token = secrets.token_urlsafe(32)
    expires = datetime.now() + timedelta(hours=24)
    
    employee.password_reset_token = token
    employee.password_reset_expires = expires
    db.session.commit()
    
    # Send password reset email
    reset_link = url_for('main.reset_password', token=token, _external=True)
    email_body = f'''
    <h2>Password Reset Request</h2>
    <p>Dear {employee.name},</p>
    <p>Your password has been reset by an administrator. Please click the link below to set a new password:</p>
    <p><a href="{reset_link}">{reset_link}</a></p>
    <p>This link will expire in 24 hours.</p>
    <p>Thank you,<br>SBS Corp Admin</p>
    '''
    
    send_email(employee.email, 'SBS Corp - Reset Your Password', email_body)
    
    flash(f'Password reset link sent to {employee.email}', 'success')
    log_admin_activity(f'Reset password for {employee.name}')
    return redirect(url_for('admin.employees'))

# Delete Employee
@admin_bp.route('/employees/delete/<string:id>', methods=['POST'])
@login_required
@admin_required
def delete_employee(id):
    employee = User.query.get_or_404(id)
    name = employee.name
    
    try:
        db.session.delete(employee)
        db.session.commit()
        flash(f'Employee {name} deleted successfully', 'success')
        log_admin_activity(f'Deleted employee {name}')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting employee: {str(e)}', 'danger')
    
    return redirect(url_for('admin.employees'))

# Report Management
@admin_bp.route('/reports')
@login_required
@admin_required
def reports():
    reports = Report.query.join(User, Report.employee_id == User.id).add_columns(
        Report.id, Report.submission_date, Report.filename, Report.status, User.name
    ).order_by(Report.submission_date.desc()).all()
    
    return render_template('admin/reports.html', reports=reports)

# View Report
@admin_bp.route('/reports/view/<string:id>')
@login_required
@admin_required
def view_report(id):
    report = Report.query.get_or_404(id)
    employee = User.query.get(report.employee_id)
    
    return render_template('admin/view_report.html', report=report, employee=employee)

# Review Report
@admin_bp.route('/reports/review/<string:id>', methods=['POST'])
@login_required
@admin_required
def review_report(id):
    report = Report.query.get_or_404(id)
    status = request.form.get('status')
    feedback = request.form.get('feedback')
    
    if status not in ['approved', 'rejected']:
        flash('Invalid status', 'danger')
        return redirect(url_for('admin.view_report', id=id))
    
    report.status = status
    report.feedback = feedback
    report.reviewed_by = current_user.id
    report.review_date = datetime.now()
    
    db.session.commit()
    
    # Notify employee
    employee = User.query.get(report.employee_id)
    notification = Notification(
        id=str(uuid.uuid4()),
        user_id=employee.id,
        message=f'Your report "{report.filename}" has been {status}. {feedback if feedback else ""}',
        type='success' if status == 'approved' else 'warning'
    )
    db.session.add(notification)
    db.session.commit()
    
    flash(f'Report {status}', 'success')
    log_admin_activity(f'{status.capitalize()} report {report.filename}')
    return redirect(url_for('admin.reports'))

# Activity Logs
@admin_bp.route('/activity-logs')
@login_required
@admin_required
def activity_logs():
    logs = ActivityLog.query.join(User, ActivityLog.user_id == User.id).add_columns(
        ActivityLog.id, ActivityLog.action, ActivityLog.details, 
        ActivityLog.timestamp, ActivityLog.ip_address, User.name
    ).order_by(ActivityLog.timestamp.desc()).limit(100).all()
    
    return render_template('admin/activity_logs.html', logs=logs)

# Admin Profile
@admin_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@admin_required
def profile():
    if request.method == 'POST':
        name = request.form.get('name')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Update name
        if name and name != current_user.name:
            current_user.name = name
            db.session.commit()
            flash('Name updated successfully', 'success')
        
        # Update password
        if current_password and new_password and confirm_password:
            if not check_password_hash(current_user.password, current_password):
                flash('Current password is incorrect', 'danger')
                return redirect(url_for('admin.profile'))
            
            if new_password != confirm_password:
                flash('New passwords do not match', 'danger')
                return redirect(url_for('admin.profile'))
            
            if len(new_password) < 6:
                flash('Password must be at least 6 characters', 'danger')
                return redirect(url_for('admin.profile'))
            
            current_user.password = generate_password_hash(new_password)
            db.session.commit()
            flash('Password updated successfully', 'success')
            log_admin_activity('Updated password')
    
    return render_template('admin/profile.html')