import os
import msal
import requests
import calendar
import logging
import time
import uuid
from datetime import datetime, timedelta, date
from threading import Thread
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from flask import Flask, render_template, request, redirect, url_for, session, flash
import schedule

from models import db, Employee, Report

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", os.getenv('FLASK_SECRET_KEY', 'your-secret-key'))

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize database
db.init_app(app)

# Create all tables
with app.app_context():
    db.create_all()

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

# Record report submission in database
def record_submission(employee_id, filename):
    with app.app_context():
        new_report = Report(
            employee_id=employee_id,
            filename=filename,
            submission_date=datetime.now()
        )
        db.session.add(new_report)
        db.session.commit()
        return new_report.id

# Send Email Reminder using SendGrid
def send_email(to_email, subject, body):
    sendgrid_key = os.environ.get('SENDGRID_API_KEY')
    sender = os.getenv('EMAIL_SENDER', 'noreply@sbscorp.com')
    
    if not sendgrid_key:
        logging.warning("SendGrid API key not found - email sending skipped")
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

# Schedule Weekly Reminders
def schedule_reminders():
    with app.app_context():
        employees = Employee.query.all()
        
        now = datetime.now()
        # Get next Sunday (end of current week)
        next_sunday = now.date() + timedelta(days=(6 - now.date().weekday()) % 7)
        current_date = now.strftime('%Y-%m-%d')
        
        for employee in employees:
            # Check if employee has already submitted a report this week
            week_start = (now.date() - timedelta(days=now.date().weekday())).strftime('%Y-%m-%d')
            has_submitted = Report.query.filter(
                Report.employee_id == str(employee.id),
                Report.submission_date >= week_start
            ).first() is not None
            
            # HTML email content
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #2c3e50; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; background-color: #f9f9f9; }}
                    .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
                    .button {{ display: inline-block; background-color: #3498db; color: white; padding: 10px 20px; 
                            text-decoration: none; border-radius: 5px; margin-top: 20px; }}
                    .warning {{ color: #e74c3c; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>SBS Corp Weekly Status Report</h2>
                    </div>
                    <div class="content">
                        <p>Hi {employee.name},</p>
                        
                        <p>This is a {'reminder' if not has_submitted else 'confirmation'} regarding your weekly status report.</p>
                        
                        {'<p><strong class="warning">You have not yet submitted your report for this week.</strong> Please submit it as soon as possible.</p>' 
                        if not has_submitted else '<p>Thank you for submitting your report this week!</p>'}
                        
                        <p>Next report due date: <strong>{next_sunday.strftime('%A, %B %d, %Y')} by 11:59 PM</strong></p>
                        
                        <p>Please log in to the Weekly Status Report Portal to {'upload' if not has_submitted else 'view'} your report.</p>
                        
                        <a href="https://weekly-status-report.replit.app" class="button">Access Portal</a>
                    </div>
                    <div class="footer">
                        <p>This is an automated message from the SBS Corp Weekly Status Report system.</p>
                        <p>&copy; {now.year} SBS Corp. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            send_email(
                employee.email,
                f"Weekly Report {'Reminder' if not has_submitted else 'Confirmation'} - {current_date}",
                html_content
            )
            logging.info(f"{'Reminder' if not has_submitted else 'Confirmation'} email sent to {employee.email}")

# Set up the scheduler to send reminders on Sunday evening
schedule.every().sunday.at("20:00").do(schedule_reminders)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(60)

# Start scheduler in a separate thread
scheduler_thread = Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# Get recent submissions for an employee
def get_recent_submissions(employee_id, limit=5):
    with app.app_context():
        recent_submissions = Report.query.filter_by(employee_id=employee_id).order_by(
            Report.submission_date.desc()
        ).limit(limit).all()
        
        return [{"id": str(submission.id), 
                "date": submission.submission_date.strftime('%Y-%m-%d %H:%M:%S'), 
                "filename": submission.filename} for submission in recent_submissions]

# Function to get calendar data with submissions marked
def get_calendar_data(employee_id, year, month):
    with app.app_context():
        # Get all submissions for the employee
        reports = Report.query.filter_by(employee_id=employee_id).all()
        submissions = [report.submission_date.date() for report in reports]
        
        # Calculate the calendar grid
        cal = calendar.monthcalendar(year, month)
        
        # Get the first Sunday of the month (or before)
        first_day = date(year, month, 1)
        # If first_day is Sunday (6), don't adjust; otherwise adjust back to previous Sunday
        offset = first_day.weekday() + 1 if first_day.weekday() < 6 else 0
        first_sunday = first_day - timedelta(days=offset)
        
        # Calculate which Sundays should have submissions
        sundays = []
        current_sunday = first_sunday
        while current_sunday.month <= month and current_sunday.year == year:
            if current_sunday.month == month:
                sundays.append(current_sunday)
            current_sunday += timedelta(days=7)
        
        # Mark submissions as completed or missing
        calendar_data = {
            'weeks': cal,
            'month_name': calendar.month_name[month],
            'year': year,
            'month': month,
            'submissions': submissions,
            'mondays': sundays  # We keep the same variable name for compatibility
        }
        
        return calendar_data

# Routes
@app.route('/')
def index():
    if 'employee_id' in session:
        return redirect(url_for('dashboard'))
    # Pass the current datetime to the template for dynamic copyright year
    now = datetime.now()
    return render_template('index.html', now=now)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # If already logged in, redirect to dashboard
    if 'employee_id' in session:
        return redirect(url_for('dashboard'))
        
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
        
        try:
            folder_id = create_onedrive_folder(name)
            new_employee = Employee(
                name=name,
                email=email,
                password=password,
                folder_id=folder_id
            )
            db.session.add(new_employee)
            db.session.commit()
            
            flash("Sign-up successful! Please log in.", "success")
            return redirect(url_for('index'))
        except Exception as e:
            logging.error(f"Signup error: {str(e)}")
            flash(f"Error: {str(e)}", "danger")
    
    return render_template('signup.html', now=datetime.now())

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    
    logging.debug(f"Login attempt for email: {email}")
    
    if not all([email, password]):
        logging.debug("Missing email or password")
        flash("Email and password are required", "danger")
        return redirect(url_for('index'))
    
    try:
        # Find user by email
        user = Employee.query.filter_by(email=email).first()
        
        if not user:
            logging.debug(f"No user found with email: {email}")
            flash("Email not registered", "danger")
            return redirect(url_for('index'))
        
        # Check password
        if user.password == password:
            session['employee_id'] = str(user.id)
            session['employee_name'] = user.name
            session['folder_id'] = user.folder_id
            flash(f"Welcome back, {user.name}!", "success")
            return redirect(url_for('dashboard'))
        else:
            logging.debug("Password mismatch")
            flash("Invalid password", "danger")
            return redirect(url_for('index'))
    except Exception as e:
        logging.error(f"Login error: {str(e)}")
        flash("An error occurred during login. Please try again.", "danger")
    
    return redirect(url_for('index'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'employee_id' not in session:
        flash("Please log in to access your dashboard", "warning")
        return redirect(url_for('index'))
    
    recent_submissions = get_recent_submissions(session['employee_id'])
    now = datetime.now()
    
    if request.method == 'POST':
        if 'report' not in request.files:
            flash("No file selected", "danger")
            return render_template('dashboard.html', name=session['employee_name'], 
                                 submissions=recent_submissions, now=now)
        
        file = request.files['report']
        if file.filename == '':
            flash("No file selected", "danger")
            return render_template('dashboard.html', name=session['employee_name'], 
                                 submissions=recent_submissions, now=now)
        
        if file:
            # Get file extension
            file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'pdf'
            
            # Generate unique filename with date
            filename = f"Weekly_Report_{session['employee_name']}_{now.strftime('%Y%m%d_%H%M%S')}.{file_ext}"
            try:
                file_info = upload_to_onedrive(file.read(), session['folder_id'], filename)
                record_submission(session['employee_id'], filename)
                flash("Report uploaded successfully!", "success")
                # Refresh submissions list
                recent_submissions = get_recent_submissions(session['employee_id'])
            except Exception as e:
                logging.error(f"File upload error: {str(e)}")
                flash(f"Error: {str(e)}", "danger")
    
    # Calculate next Sunday for due date display
    today = now.date()
    next_sunday = today + timedelta(days=(6 - today.weekday()) % 7)
    
    # Get calendar data for current month
    calendar_data = get_calendar_data(session['employee_id'], now.year, now.month)
    
    return render_template('dashboard.html', 
                         name=session['employee_name'], 
                         submissions=recent_submissions, 
                         now=now, 
                         next_sunday=next_sunday,
                         calendar=calendar_data)

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for('index'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)