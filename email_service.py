import os
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Configure logging
logger = logging.getLogger(__name__)

# Email configuration from environment variables
SMTP_SERVER = os.environ.get('SMTP_SERVER')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'True').lower() in ('true', '1', 't')
SENDER_NAME = os.environ.get('SENDER_NAME', 'SBS Corp Weekly Status Report System')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'statusreports@mysbscorp.com')


def send_email(to_email, subject, html_content=None, text_content=None):
    """
    Send an email using the configured SMTP server.
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        html_content (str, optional): HTML content of the email
        text_content (str, optional): Plain text content of the email
        
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    # Check if the email service is configured
    if not SMTP_SERVER or not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.warning("Email service not configured. Set SMTP_SERVER, SMTP_USERNAME, and SMTP_PASSWORD environment variables.")
        return False
    
    # Create the message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg['To'] = to_email
    
    # Always provide a plain text version as a fallback
    if text_content:
        msg.attach(MIMEText(text_content, 'plain'))
    elif html_content:
        # Generate a plain text version from the HTML content
        plain_text = html_content.replace('<br>', '\n').replace('<p>', '\n').replace('</p>', '\n')
        plain_text = ''.join(c for c in plain_text if ord(c) < 128)  # Remove non-ASCII characters
        msg.attach(MIMEText(plain_text, 'plain'))
    
    # Add HTML content if provided
    if html_content:
        msg.attach(MIMEText(html_content, 'html'))
    
    try:
        # Connect to the SMTP server
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.ehlo()
        
        # Use TLS if configured
        if SMTP_USE_TLS:
            server.starttls()
            server.ehlo()
        
        # Login to the SMTP server
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        
        # Send the email
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        
        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False


def send_reminder_email(to_email, employee_name, due_date_str=None):
    """
    Send a reminder email to an employee who missed their weekly report submission.
    
    Args:
        to_email (str): Employee email address
        employee_name (str): Employee name
        due_date_str (str, optional): Due date string
        
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    # If due date not provided, use a generic message
    due_date_text = f"by <strong>{due_date_str}</strong>" if due_date_str else "soon"
    
    subject = "[REMINDER] Weekly Status Report Due"
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9;">
            <h2 style="color: #d9534f; border-bottom: 1px solid #eee; padding-bottom: 10px;">Weekly Report Reminder</h2>
            
            <p>Hello {employee_name},</p>
            
            <p>This is a friendly reminder that your weekly status report is due {due_date_text}.</p>
            
            <p>Please login to the SBS Corp Weekly Status Report System to submit your report.</p>
            
            <p style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee;">
                Thank you,<br>
                <strong>SBS Corp Admin Team</strong>
            </p>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, html_content)


def send_report_approved_email(to_email, employee_name, report_date, feedback=None):
    """
    Send an email notification when a report is approved.
    
    Args:
        to_email (str): Employee email address
        employee_name (str): Employee name
        report_date (str): Report submission date
        feedback (str, optional): Optional feedback from the reviewer
        
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    subject = "Weekly Report Approved"
    
    # Format feedback section
    feedback_section = ""
    if feedback:
        feedback_section = f"""
        <div style="margin: 15px 0; padding: 10px; border-left: 4px solid #5cb85c; background-color: #f9f9f9;">
            <h3 style="margin-top: 0; color: #5cb85c;">Feedback from Admin:</h3>
            <p>{feedback}</p>
        </div>
        """
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9;">
            <h2 style="color: #5cb85c; border-bottom: 1px solid #eee; padding-bottom: 10px;">Weekly Report Approved ✓</h2>
            
            <p>Hello {employee_name},</p>
            
            <p>Your weekly status report submitted on <strong>{report_date}</strong> has been <strong style="color: #5cb85c;">approved</strong>.</p>
            
            {feedback_section}
            
            <p style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee;">
                Thank you,<br>
                <strong>SBS Corp Admin Team</strong>
            </p>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, html_content)


def send_report_rejected_email(to_email, employee_name, report_date, feedback=None):
    """
    Send an email notification when a report is rejected.
    
    Args:
        to_email (str): Employee email address
        employee_name (str): Employee name
        report_date (str): Report submission date
        feedback (str, optional): Optional feedback from the reviewer
        
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    subject = "Weekly Report Requires Revision"
    
    # Format feedback section
    feedback_section = ""
    if feedback:
        feedback_section = f"""
        <div style="margin: 15px 0; padding: 10px; border-left: 4px solid #d9534f; background-color: #f9f9f9;">
            <h3 style="margin-top: 0; color: #d9534f;">Feedback from Admin:</h3>
            <p>{feedback}</p>
        </div>
        """
    else:
        feedback_section = """
        <div style="margin: 15px 0; padding: 10px; border-left: 4px solid #d9534f; background-color: #f9f9f9;">
            <h3 style="margin-top: 0; color: #d9534f;">Feedback from Admin:</h3>
            <p>No specific feedback was provided. Please contact your administrator for more details.</p>
        </div>
        """
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9;">
            <h2 style="color: #d9534f; border-bottom: 1px solid #eee; padding-bottom: 10px;">Weekly Report Requires Revision</h2>
            
            <p>Hello {employee_name},</p>
            
            <p>Your weekly status report submitted on <strong>{report_date}</strong> has been <strong style="color: #d9534f;">rejected</strong> and requires revision.</p>
            
            {feedback_section}
            
            <p>Please log in to the system, review the feedback, and submit a revised report as soon as possible.</p>
            
            <p style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee;">
                Thank you,<br>
                <strong>SBS Corp Admin Team</strong>
            </p>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, html_content)


def send_welcome_email(to_email, employee_name, password=None):
    """
    Send a welcome email to a new employee.
    
    Args:
        to_email (str): Employee email address
        employee_name (str): Employee name
        password (str, optional): Initial password if provided
        
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    subject = "Welcome to SBS Corp Weekly Status Report System"
    
    # Format password section if provided
    password_section = ""
    if password:
        password_section = f"""
        <p><strong>Your login details:</strong></p>
        <ul style="margin: 10px 0; padding: 10px; background-color: #f0f0f0; border-radius: 5px;">
            <li><strong>Email:</strong> {to_email}</li>
            <li><strong>Initial Password:</strong> {password}</li>
        </ul>
        <p>For security reasons, please change your password after your first login.</p>
        """
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9;">
            <h2 style="color: #337ab7; border-bottom: 1px solid #eee; padding-bottom: 10px;">Welcome to SBS Corp!</h2>
            
            <p>Hello {employee_name},</p>
            
            <p>An account has been created for you on the SBS Corp Weekly Status Report System.</p>
            
            {password_section}
            
            <h3 style="color: #5cb85c; margin-top: 20px;">What's Next?</h3>
            
            <ol>
                <li>Login to the system using your credentials</li>
                <li>Submit your weekly status report by the end of each week</li>
                <li>Check for any feedback or notifications from administrators</li>
            </ol>
            
            <p style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee;">
                Thank you,<br>
                <strong>SBS Corp Admin Team</strong>
            </p>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, html_content)


def is_email_configured():
    """
    Check if the email service is configured.
    
    Returns:
        bool: True if the email service is configured, False otherwise
    """
    return bool(SMTP_SERVER and SMTP_USERNAME and SMTP_PASSWORD)