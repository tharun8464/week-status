import os
import logging
from datetime import datetime, timedelta

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)

def get_slack_token():
    """Get the Slack bot token from environment."""
    return os.environ.get('SLACK_BOT_TOKEN')

def get_slack_channel():
    """Get the Slack channel ID from environment."""
    return os.environ.get('SLACK_CHANNEL_ID')

def get_slack_client():
    """Initialize and return the Slack client with current token."""
    token = get_slack_token()
    if token:
        return WebClient(token=token)
    return None


def is_slack_configured():
    """
    Check if Slack is configured.
    
    Returns:
        bool: True if Slack is configured, False otherwise
    """
    token = get_slack_token()
    channel = get_slack_channel()
    return bool(token and channel)


def send_slack_message(message, blocks=None, thread_ts=None):
    """
    Send a message to the configured Slack channel.
    
    Args:
        message (str): The message text to send
        blocks (list, optional): Formatted blocks for rich messages
        thread_ts (str, optional): Timestamp of thread to reply to
    
    Returns:
        bool: True if the message was sent successfully, False otherwise
    """
    if not is_slack_configured():
        logger.warning("Slack not configured. Set SLACK_BOT_TOKEN and SLACK_CHANNEL_ID environment variables.")
        return False
    
    client = get_slack_client()
    channel = get_slack_channel()
    
    try:
        # Send the message to the specified channel
        response = client.chat_postMessage(
            channel=channel,
            text=message,
            blocks=blocks,
            thread_ts=thread_ts
        )
        
        logger.info(f"Slack message sent successfully: {response['ts']}")
        return True
    except SlackApiError as e:
        logger.error(f"Failed to send Slack message: {str(e)}")
        return False


def send_reminder_notification(employee_name, due_date_str=None):
    """
    Send a reminder notification to Slack.
    
    Args:
        employee_name (str): Name of the employee who needs to submit a report
        due_date_str (str, optional): Due date for the report
        
    Returns:
        bool: True if the notification was sent successfully, False otherwise
    """
    # If due date not provided, use next Sunday
    if not due_date_str:
        now = datetime.now()
        # For Sunday (weekday 6 in Python's datetime, where Monday is 0)
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7
        next_sunday = now + timedelta(days=days_until_sunday)
        next_sunday = next_sunday.replace(hour=23, minute=59, second=59, microsecond=0)
        due_date_str = next_sunday.strftime("%A, %B %d, %Y at %I:%M %p")
    
    # Get current week number and year
    now = datetime.now()
    current_week = now.isocalendar()[1]  # ISO week number
    current_year = now.year
    
    # Create rich formatted blocks for the message
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"⚠️ Weekly Status Report Reminder - Week {current_week}, {current_year}",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Employee:* {employee_name}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"This is a friendly reminder that your *Weekly Status Report for Week {current_week}, {current_year}* is due by *{due_date_str}*."
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Automated message from SBS Weekly Report System"
                }
            ]
        }
    ]
    
    return send_slack_message(
        message=f"Weekly Status Report Reminder for {employee_name}",
        blocks=blocks
    )


def send_report_status_notification(employee_name, report_filename, status, feedback=None):
    """
    Send a notification about a report status change.
    
    Args:
        employee_name (str): Name of the employee who submitted the report
        report_filename (str): Name of the report file
        status (str): Status of the report ('approved' or 'rejected')
        feedback (str, optional): Feedback from the reviewer
        
    Returns:
        bool: True if the notification was sent successfully, False otherwise
    """
    # Determine emoji and color based on status
    if status == 'approved':
        emoji = "✅"
        color = "#36a64f"  # Green
        status_text = "Approved"
    else:
        emoji = "❌"
        color = "#d9534f"  # Red
        status_text = "Rejected"
    
    # Create rich formatted blocks for the message
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} Weekly Status Report {status_text}",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Employee:* {employee_name}\n*Report:* {report_filename}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"The report has been *{status.lower()}*."
            }
        }
    ]
    
    # Add feedback if provided
    if feedback:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Feedback:*"
            }
        })
        blocks.append({
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": feedback
            }
        })
    
    blocks.append({
        "type": "divider"
    })
    
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "Automated message from SBS Weekly Report System"
            }
        ]
    })
    
    return send_slack_message(
        message=f"Weekly Status Report {status_text} for {employee_name}",
        blocks=blocks
    )


def send_new_employee_notification(employee_name, employee_email):
    """
    Send a notification about a new employee.
    
    Args:
        employee_name (str): Name of the new employee
        employee_email (str): Email of the new employee
        
    Returns:
        bool: True if the notification was sent successfully, False otherwise
    """
    # Create rich formatted blocks for the message
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🎉 New Employee Added",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Name:* {employee_name}\n*Email:* {employee_email}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "A new employee has been added to the Weekly Status Report System."
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Automated message from SBS Weekly Report System"
                }
            ]
        }
    ]
    
    return send_slack_message(
        message=f"New Employee Added: {employee_name}",
        blocks=blocks
    )