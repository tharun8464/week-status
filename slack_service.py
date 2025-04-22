import os
import logging
from datetime import datetime

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)

# Slack credentials from environment variables
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
SLACK_CHANNEL_ID = os.environ.get('SLACK_CHANNEL_ID')

# Initialize the Slack client if token is available
slack_client = None
if SLACK_BOT_TOKEN:
    slack_client = WebClient(token=SLACK_BOT_TOKEN)


def is_slack_configured():
    """
    Check if Slack is configured.
    
    Returns:
        bool: True if Slack is configured, False otherwise
    """
    return bool(SLACK_BOT_TOKEN and SLACK_CHANNEL_ID and slack_client)


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
    
    try:
        # Send the message to the specified channel
        response = slack_client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
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
    # If due date not provided, use next Monday
    if not due_date_str:
        now = datetime.now()
        days_until_monday = (7 - now.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = now.replace(hour=9, minute=0, second=0, microsecond=0)
        next_monday = next_monday.replace(day=next_monday.day + days_until_monday)
        due_date_str = next_monday.strftime("%A, %B %d, %Y at %I:%M %p")
    
    # Create rich formatted blocks for the message
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "⚠️ Weekly Status Report Reminder",
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
                "text": f"This is a friendly reminder that a weekly status report is due by *{due_date_str}*."
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