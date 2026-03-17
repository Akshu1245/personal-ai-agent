"""
JARVIS Email Draft Module
Generate and send emails via SMTP

Author: Rashi AI
Built for: Akshay
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional

# SMTP configuration (should be in environment variables)
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')


def generate_draft(subject: str, body: str, recipient: str = None) -> Dict[str, Any]:
    """
    Generate email draft content
    
    Args:
        subject: Email subject
        body: Email body
        recipient: Recipient email (optional)
        
    Returns:
        Dict with draft content
    """
    return {
        'success': True,
        'subject': subject,
        'body': body,
        'recipient': recipient,
        'draft': f"To: {recipient or '[recipient]'}\nSubject: {subject}\n\n{body}"
    }


def send_email(subject: str, body: str, to_email: str, from_email: str = None) -> Dict[str, Any]:
    """
    Send an email
    
    Args:
        subject: Email subject
        body: Email body
        to_email: Recipient email
        from_email: Sender email (optional)
        
    Returns:
        Dict with send result
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        return {
            'success': False,
            'error': 'SMTP not configured. Set SMTP_USERNAME and SMTP_PASSWORD in .env'
        }
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = from_email or SMTP_USERNAME
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Attach body
        msg.attach(MIMEText(body, 'plain'))
        
        # Connect and send
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return {
            'success': True,
            'message': f'Email sent to {to_email}'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def generate_professional_email(recipient_name: str, purpose: str, details: str = '') -> Dict[str, Any]:
    """
    Generate a professional email using AI
    
    Args:
        recipient_name: Name of recipient
        purpose: Purpose of email
        details: Additional details
        
    Returns:
        Dict with generated email
    """
    templates = {
        'meeting': f"Dear {recipient_name},\n\nI hope this email finds you well. I would like to schedule a meeting to discuss {details}.\n\nPlease let me know your availability.\n\nBest regards,\nAkshay",
        'follow_up': f"Dear {recipient_name},\n\nI wanted to follow up on our previous conversation regarding {details}.\n\nPlease let me know if you need any further information.\n\nBest regards,\nAkshay",
        'request': f"Dear {recipient_name},\n\nI am writing to request {details}.\n\nI would greatly appreciate your assistance in this matter.\n\nThank you for your time.\n\nBest regards,\nAkshay",
        'thank_you': f"Dear {recipient_name},\n\nThank you for {details}.\n\nI truly appreciate your help and support.\n\nBest regards,\nAkshay"
    }
    
    body = templates.get(purpose.lower(), templates['meeting'])
    
    return generate_draft(
        subject=f"{purpose.title()} - {recipient_name}",
        body=body,
        recipient=recipient_name
    )
