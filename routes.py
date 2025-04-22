import os
import logging
import msal
import requests
import calendar
from datetime import datetime, timedelta, date
import uuid
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from models import db, Employee, Report
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the Blueprint
bp = Blueprint('main', __name__)

# Jinja filter for enumerate
@bp.app_template_global()
def enumerate(iterable, start=0):
    return __builtins__.enumerate(iterable, start)

# OneDrive API Configuration
CLIENT_ID = os.getenv('CLIENT_ID', 'ea86ce4c-a4cc-430a-bc40-d788e4fa38d0')
CLIENT_SECRET = os.getenv('CLIENT_SECRET', 'm_n8Q~nR4ozZiUIdadf1FptciOAzObWc0ME1Wa.H')
TENANT_ID = os.getenv('TENANT_ID', '0c94296c-b6cd-4b8c-a60b-972d913ca913')
DRIVE_ID = os.getenv('DRIVE_ID', '7b22fb5e-bf21-4136-ac81-e7026f575dc7')
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

# MSAL Client
client = msal.ConfidentialClientApplication(
    CLIENT_ID,
    authority=AUTHORITY,
    client_credential=CLIENT_SECRET
)

# OneDrive Authentication
def get_access_token():
    token = client.acquire_token_for_client(scopes=SCOPES)
    if "access_token" in token:
        return token["access_token"]
    else:
        error = token.get("error", "Unknown error")
        error_description = token.get("error_description", "No description")
        raise Exception(f"Could not acquire token: {error} - {error_description}")

# Ensure Main "Weekly Status Reports" Folder Exists
def ensure_main_folder():
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    endpoint = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root:/Weekly Status Reports:"
    response = requests.get(endpoint, headers=headers)

    if response.status_code == 200:
        return response.json()["id"]

    # If folder doesn't exist, create it
    if response.status_code == 404:
        logging.info("Folder not found. Creating 'Weekly Status Reports'...")
        endpoint = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root/children"
        data = {
            "name": "Weekly Status Reports",
            "folder": {},
            "@microsoft.graph.conflictBehavior": "rename"
        }
        response = requests.post(endpoint, headers=headers, json=data)
        if response.status_code == 201:
            return response.json()["id"]
        else:
            raise Exception(f"Main folder creation failed: {response.status_code} - {response.text}")
    else:
        raise Exception(f"Failed to check for main folder: {response.status_code} - {response.text}")

# Create Employee Subfolder
def create_onedrive_folder(employee_name):
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    main_folder_id = ensure_main_folder()

    # Create employee subfolder
    endpoint = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{main_folder_id}/children"
    data = {
        "name": employee_name,
        "folder": {},
        "@microsoft.graph.conflictBehavior": "rename"
    }
    response = requests.post(endpoint, headers=headers, json=data)
    if response.status_code == 201:
        return response.json()["id"]
    else:
        raise Exception(f"Employee folder creation failed: {response.status_code} - {response.text}")

# Upload File to OneDrive
def upload_to_onedrive(file, folder_id, filename):
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"}
    endpoint = f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{folder_id}:/{filename}:/content"
    response = requests.put(endpoint, headers=headers, data=file)
    if response.status_code == 201:
        return response.json()
    else:
        raise Exception(f"File upload failed: {response.status_code} - {response.text}")

# Send Email Reminder using SendGrid
def send_email(to_email, subject, body):
    sendgrid_key = os.environ.get('SENDGRID_API_KEY')
    sender = os.getenv('EMAIL_SENDER', 'noreply@sbscorp.com')
    
    if not sendgrid_key:
        logging.warning("SendGrid API key not found. Email will not be sent.")
        return False
    
    message = Mail(
        from_email=sender,
        to_emails=to_email,
        subject=subject,
        html_content=body)
    
    try:
        sg = SendGridAPIClient(sendgrid_key)
        response = sg.send(message)
        logging.info(f"Email sent with status code {response.status_code}")
        return True
    except Exception as e:
        logging.error(f"Email sending failed: {str(e)}")
        return False

# Function to get calendar data with submissions marked
def get_calendar_data(employee_id, year, month):
    # Get all submissions for the employee
    submissions = Report.query.filter_by(employee_id=employee_id).all()
    submission_dates = [report.submission_date.date() for report in submissions]
    
    # Calculate the calendar grid
    cal = calendar.monthcalendar(year, month)
    
    # Get the first Monday of the month (or before)
    first_day = date(year, month, 1)
    first_monday = first_day - timedelta(days=first_day.weekday())
    
    # Calculate which Mondays should have submissions
    mondays = []
    current_monday = first_monday
    while current_monday.month == month or (current_monday.month < month and current_monday.year == year):
        if current_monday.month == month:
            mondays.append(current_monday)
        current_monday += timedelta(days=7)
    
    # Mark submissions as completed or missing
    calendar_data = {
        'weeks': cal,
        'month_name': calendar.month_name[month],
        'year': year,
        'month': month,
        'submissions': submission_dates,
        'mondays': mondays
    }
    
    return calendar_data

# Routes
@bp.route('/')
def index():
    if 'employee_id' in session:
        return redirect(url_for('main.dashboard'))
    # Pass the current datetime to the template for dynamic copyright year
    now = datetime.now()
    return render_template('index.html', now=now)

@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    # If already logged in, redirect to dashboard
    if 'employee_id' in session:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        
        # Simple validation
        if not all([name, email, password]):
            flash("All fields are required", "danger")
            return render_template('signup.html', now=datetime.now())
        
        # Check if email already exists
        existing_user = Employee.query.filter_by(email=email).first()
        
        if existing_user:
            flash("Email already registered", "danger")
            return render_template('signup.html', now=datetime.now())
        
        employee_id = str(uuid.uuid4())
        try:
            folder_id = create_onedrive_folder(name)
            new_employee = Employee(
                id=employee_id,
                name=name,
                email=email,
                password=password,
                folder_id=folder_id
            )
            db.session.add(new_employee)
            db.session.commit()
            flash("Sign-up successful! Please log in.", "success")
            return redirect(url_for('main.index'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Signup error: {str(e)}")
            flash(f"Error: {str(e)}", "danger")
    
    return render_template('signup.html', now=datetime.now())

@bp.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    
    logging.debug(f"Login attempt for email: {email}")
    
    if not all([email, password]):
        logging.debug("Missing email or password")
        flash("Email and password are required", "danger")
        return redirect(url_for('main.index'))
    
    try:
        # Find the user by email
        employee = Employee.query.filter_by(email=email).first()
        
        if not employee:
            logging.debug(f"No user found with email: {email}")
            flash("Email not registered", "danger")
            return redirect(url_for('main.index'))
        
        # Check password
        if employee.password == password:
            session['employee_id'] = str(employee.id)
            session['employee_name'] = employee.name
            session['folder_id'] = employee.folder_id
            flash(f"Welcome back, {employee.name}!", "success")
            return redirect(url_for('main.dashboard'))
        else:
            logging.debug("Password mismatch")
            flash("Invalid password", "danger")
            return redirect(url_for('main.index'))
    except Exception as e:
        logging.error(f"Login error: {str(e)}")
        flash("An error occurred during login. Please try again.", "danger")
    
    return redirect(url_for('main.index'))

@bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'employee_id' not in session:
        flash("Please log in to access your dashboard", "warning")
        return redirect(url_for('main.index'))
    
    employee_id = session['employee_id']
    employee = Employee.query.get(employee_id)
    
    if not employee:
        session.clear()
        flash("User not found. Please log in again.", "warning")
        return redirect(url_for('main.index'))
    
    # Get recent submissions
    recent_submissions = Report.query.filter_by(employee_id=employee_id).order_by(Report.submission_date.desc()).limit(5).all()
    submissions_data = [{"id": str(report.id), "date": report.submission_date.strftime('%Y-%m-%d %H:%M:%S'), "filename": report.filename} for report in recent_submissions]
    
    now = datetime.now()
    
    if request.method == 'POST':
        if 'report' not in request.files:
            flash("No file selected", "danger")
            return render_template('dashboard.html', name=session['employee_name'], 
                                 submissions=submissions_data, now=now)
        
        file = request.files['report']
        if file.filename == '':
            flash("No file selected", "danger")
            return render_template('dashboard.html', name=session['employee_name'], 
                                 submissions=submissions_data, now=now)
        
        if file:
            # Get file extension
            file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'pdf'
            
            # Generate unique filename with date
            filename = f"Weekly_Report_{session['employee_name']}_{now.strftime('%Y%m%d_%H%M%S')}.{file_ext}"
            try:
                # Upload to OneDrive
                file_info = upload_to_onedrive(file.read(), session['folder_id'], filename)
                
                # Record in database
                new_report = Report(
                    id=str(uuid.uuid4()),
                    employee_id=employee_id,
                    submission_date=now,
                    filename=filename
                )
                db.session.add(new_report)
                db.session.commit()
                
                flash("Report uploaded successfully!", "success")
                # Refresh submissions list
                recent_submissions = Report.query.filter_by(employee_id=employee_id).order_by(Report.submission_date.desc()).limit(5).all()
                submissions_data = [{"id": str(report.id), "date": report.submission_date.strftime('%Y-%m-%d %H:%M:%S'), "filename": report.filename} for report in recent_submissions]
            except Exception as e:
                db.session.rollback()
                logging.error(f"File upload error: {str(e)}")
                flash(f"Error: {str(e)}", "danger")
    
    # Calculate next Monday for due date display
    today = now.date()
    next_monday = today + timedelta(days=(7 - today.weekday()))
    
    # Get calendar data for current month
    calendar_data = get_calendar_data(employee_id, now.year, now.month)
    
    return render_template('dashboard.html', 
                         name=session['employee_name'], 
                         submissions=submissions_data, 
                         now=now, 
                         next_monday=next_monday,
                         calendar=calendar_data)

@bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for('main.index'))

@bp.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@bp.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500