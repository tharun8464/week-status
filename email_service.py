import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Default sender info - will be overridden if environment variables are set
DEFAULT_SENDER_EMAIL = "noreply@sbscorp.example.com"
DEFAULT_SENDER_NAME = "SBS Weekly Report System"

# SMTP Settings - set these environment variables to enable email
SMTP_SERVER = os.environ.get('SMTP_SERVER')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'True').lower() == 'true'
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', DEFAULT_SENDER_EMAIL)
SENDER_NAME = os.environ.get('SENDER_NAME', DEFAULT_SENDER_NAME)

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
    # If due date not provided, use next Monday
    if not due_date_str:
        now = datetime.now(timezone.utc)
        days_until_monday = (7 - now.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = now.replace(hour=9, minute=0, second=0, microsecond=0)
        next_monday = next_monday.replace(day=next_monday.day + days_until_monday)
        due_date_str = next_monday.strftime("%A, %B %d, %Y at %I:%M %p")
    
    subject = "⚠️ Weekly Status Report Reminder"
    
    html_content = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #2a5885;
                color: white;
                padding: 10px 20px;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: #f9f9f9;
                padding: 20px;
                border-radius: 0 0 5px 5px;
                border: 1px solid #ddd;
                border-top: none;
            }}
            .highlight {{
                color: #d9534f;
                font-weight: bold;
            }}
            .button {{
                display: inline-block;
                padding: 10px 20px;
                background-color: #2a5885;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin-top: 20px;
            }}
            .footer {{
                margin-top: 20px;
                font-size: 12px;
                color: #777;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Weekly Status Report Reminder</h2>
            </div>
            <div class="content">
                <p>Hello {employee_name},</p>
                
                <p>This is a friendly reminder that your <span class="highlight">weekly status report</span> is due. Please submit your report as soon as possible.</p>
                
                <p><strong>Due Date:</strong> {due_date_str}</p>
                
                <p>Submitting your weekly report on time helps management track project progress and address any potential issues promptly. Your cooperation is highly appreciated.</p>
                
                <p>If you've already submitted your report, please disregard this message.</p>
                
                <a href="https://report.sbscorp.example.com" class="button">Submit Your Report</a>
                
                <p>Thank you for your attention to this matter.</p>
                
                <p>Best regards,<br>SBS Corp Management</p>
            </div>
            <div class="footer">
                <p>This is an automated message from the SBS Weekly Report System. Please do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
Hello {employee_name},

This is a friendly reminder that your weekly status report is due. Please submit your report as soon as possible.

Due Date: {due_date_str}

Submitting your weekly report on time helps management track project progress and address any potential issues promptly. Your cooperation is highly appreciated.

If you've already submitted your report, please disregard this message.

Thank you for your attention to this matter.

Best regards,
SBS Corp Management

--
This is an automated message from the SBS Weekly Report System. Please do not reply to this email.
    """
    
    return send_email(to_email, subject, html_content, text_content)

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
    subject = "✅ Weekly Status Report Approved"
    
    # Prepare feedback HTML content
    feedback_div = ""
    if feedback:
        feedback_div = f'<div class="feedback"><p><strong>Feedback:</strong></p><p>{feedback}</p></div>'
    
    # Prepare feedback text content
    feedback_text = ""
    if feedback:
        feedback_text = f"Feedback:\n{feedback}\n"
    
    html_content = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #5cb85c;
                color: white;
                padding: 10px 20px;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: #f9f9f9;
                padding: 20px;
                border-radius: 0 0 5px 5px;
                border: 1px solid #ddd;
                border-top: none;
            }}
            .feedback {{
                background-color: #f5f5f5;
                padding: 15px;
                border-left: 4px solid #5cb85c;
                margin: 15px 0;
            }}
            .footer {{
                margin-top: 20px;
                font-size: 12px;
                color: #777;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Weekly Status Report Approved</h2>
            </div>
            <div class="content">
                <p>Hello {employee_name},</p>
                
                <p>Your weekly status report for the period ending <strong>{report_date}</strong> has been <strong style="color: #5cb85c;">approved</strong>.</p>
                
                {feedback_div}
                
                <p>Thank you for your timely submission and thorough reporting.</p>
                
                <p>Best regards,<br>SBS Corp Management</p>
            </div>
            <div class="footer">
                <p>This is an automated message from the SBS Weekly Report System. Please do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
Hello {employee_name},

Your weekly status report for the period ending {report_date} has been approved.

{feedback_text}

Thank you for your timely submission and thorough reporting.

Best regards,
SBS Corp Management

--
This is an automated message from the SBS Weekly Report System. Please do not reply to this email.
    """
    
    return send_email(to_email, subject, html_content, text_content)

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
    subject = "❌ Weekly Status Report Requires Revision"
    
    # Prepare feedback HTML content
    feedback_div = ""
    if feedback:
        feedback_div = f'<div class="feedback"><p><strong>Feedback:</strong></p><p>{feedback}</p></div>'
    
    # Prepare feedback text content
    feedback_text = ""
    if feedback:
        feedback_text = f"Feedback:\n{feedback}\n"
    
    html_content = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #d9534f;
                color: white;
                padding: 10px 20px;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: #f9f9f9;
                padding: 20px;
                border-radius: 0 0 5px 5px;
                border: 1px solid #ddd;
                border-top: none;
            }}
            .feedback {{
                background-color: #f5f5f5;
                padding: 15px;
                border-left: 4px solid #d9534f;
                margin: 15px 0;
            }}
            .button {{
                display: inline-block;
                padding: 10px 20px;
                background-color: #2a5885;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin-top: 20px;
            }}
            .footer {{
                margin-top: 20px;
                font-size: 12px;
                color: #777;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Weekly Status Report Requires Revision</h2>
            </div>
            <div class="content">
                <p>Hello {employee_name},</p>
                
                <p>Your weekly status report for the period ending <strong>{report_date}</strong> requires revision.</p>
                
                {feedback_div}
                
                <p>Please review the feedback and submit a revised report at your earliest convenience.</p>
                
                <a href="https://report.sbscorp.example.com" class="button">Submit Revised Report</a>
                
                <p>If you have any questions, please contact your manager.</p>
                
                <p>Best regards,<br>SBS Corp Management</p>
            </div>
            <div class="footer">
                <p>This is an automated message from the SBS Weekly Report System. Please do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
Hello {employee_name},

Your weekly status report for the period ending {report_date} requires revision.

{feedback_text}

Please review the feedback and submit a revised report at your earliest convenience.

If you have any questions, please contact your manager.

Best regards,
SBS Corp Management

--
This is an automated message from the SBS Weekly Report System. Please do not reply to this email.
    """
    
    return send_email(to_email, subject, html_content, text_content)

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
    subject = "🎉 Welcome to SBS Corp Weekly Reporting System"
    
    password_section = ""
    if password:
        password_section = f"""
        <p>Your initial password is: <strong>{password}</strong></p>
        <p>For security reasons, please change your password after your first login.</p>
        """
    
    html_content = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #2a5885;
                color: white;
                padding: 10px 20px;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: #f9f9f9;
                padding: 20px;
                border-radius: 0 0 5px 5px;
                border: 1px solid #ddd;
                border-top: none;
            }}
            .info-box {{
                background-color: #f5f5f5;
                padding: 15px;
                border-left: 4px solid #2a5885;
                margin: 15px 0;
            }}
            .button {{
                display: inline-block;
                padding: 10px 20px;
                background-color: #2a5885;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin-top: 20px;
            }}
            .footer {{
                margin-top: 20px;
                font-size: 12px;
                color: #777;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Welcome to SBS Corp Weekly Reporting System</h2>
            </div>
            <div class="content">
                <p>Hello {employee_name},</p>
                
                <p>Welcome to the SBS Corp Weekly Reporting System. Your account has been created and you can now start submitting your weekly status reports.</p>
                
                <div class="info-box">
                    <p><strong>Your login information:</strong></p>
                    <p>Email: <strong>{to_email}</strong></p>
                    {password_section}
                </div>
                
                <p><strong>Important information:</strong></p>
                <ul>
                    <li>Weekly reports are due every Monday by 9:00 AM.</li>
                    <li>You will receive automated reminders if a report is not submitted on time.</li>
                    <li>Please use the provided templates for your reports.</li>
                </ul>
                
                <a href="https://report.sbscorp.example.com" class="button">Access Reporting System</a>
                
                <p>If you need any assistance, please contact your manager or the IT department.</p>
                
                <p>Best regards,<br>SBS Corp Management</p>
            </div>
            <div class="footer">
                <p>This is an automated message from the SBS Weekly Report System. Please do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Prepare password text
    password_text = ""
    if password:
        password_text = f"Password: {password}\n\nFor security reasons, please change your password after your first login."
    
    text_content = f"""
Hello {employee_name},

Welcome to the SBS Corp Weekly Reporting System. Your account has been created and you can now start submitting your weekly status reports.

Your login information:
Email: {to_email}
{password_text}

Important information:
- Weekly reports are due every Monday by 9:00 AM.
- You will receive automated reminders if a report is not submitted on time.
- Please use the provided templates for your reports.

If you need any assistance, please contact your manager or the IT department.

Best regards,
SBS Corp Management

--
This is an automated message from the SBS Weekly Report System. Please do not reply to this email.
    """
    
    return send_email(to_email, subject, html_content, text_content)

def is_email_configured():
    """
    Check if the email service is configured.
    
    Returns:
        bool: True if the email service is configured, False otherwise
    """
    return bool(SMTP_SERVER and SMTP_USERNAME and SMTP_PASSWORD)