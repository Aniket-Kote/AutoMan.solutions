import os
import logging
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
import json


app = Flask(__name__)

# Enable CORS for the /send_email endpoint only, adjust origins as needed
CORS(app)

SMTP_SERVER = 'smtpout.secureserver.net'
SMTP_PORT = 465

# Configure logging for production
logging.basicConfig(level=logging.INFO)

def sanitize_input(text):
    # Very basic sanitization (can be enhanced)
    return str(text).replace('\n', ' ').replace('\r', ' ').strip()

@app.before_request
def enforce_https():
    # Optional: enforce HTTPS in production (if behind proxy/CDN)
    if not request.is_secure and os.getenv('FLASK_ENV') == 'production':
        abort(403, "HTTPS is required.")

@app.route('/send_email', methods=['POST'])
def send_email():
    # Use environment variable for email password
    email_password = os.getenv('EMAIL_PASSWORD')
    if not email_password:
        logging.error("EMAIL_PASSWORD environment variable is not set.")
        return jsonify({'status': 'error', 'message': 'Server configuration error.'}), 500

    try:
        data = request.get_json(force=True, silent=False)
    except (TypeError, json.JSONDecodeError) as e:
        return jsonify({'status': 'error', 'message': f'Invalid JSON: {str(e)}'}), 400

    # Required fields
    user_email = data.get('user_email')
    if not user_email:
        return jsonify({'status': 'error', 'message': 'Missing required field: user_email'}), 400

    # Optional fields with defaults and sanitization
    user_name = sanitize_input(data.get('user_name', 'User'))
    user_company_name = sanitize_input(data.get('user_company_name', 'N/A'))
    message = sanitize_input(data.get('message', ''))
    admin_subject = sanitize_input(data.get('admin_subject', f"New Inquiry from {user_name}"))
    user_subject = sanitize_input(data.get('user_subject', "Thank you for contacting Automan Solutions"))

    sender = "contact@automan.solutions"
    admin_email = sender

    # Compose email bodies
    admin_body = (
        f"Details submitted by user:\n\n"
        f"Name: {user_name}\n"
        f"Email: {user_email}\n"
        f"Company: {user_company_name}\n"
        f"Requirement:\n{message}"
    )
    user_body = (
        f"Hi {user_name},\n\n"
        "Thanks for reaching out. We have received your details and will get back to you shortly.\n\n"
        "Best regards,\n"
        "Automan Solutions Team"
    )

    # Prepare admin email
    admin_msg = MIMEText(admin_body, 'plain')
    admin_msg['Subject'] = admin_subject
    admin_msg['From'] = formataddr(('Automan Solutions', sender))
    admin_msg['To'] = admin_email
    admin_msg['Reply-To'] = user_email
    admin_msg['Message-ID'] = make_msgid(domain='automan.solutions')
    admin_msg['Return-Path'] = sender

    # Prepare user email
    user_msg = MIMEText(user_body, 'plain')
    user_msg['Subject'] = user_subject
    user_msg['From'] = formataddr(('Automan Solutions', sender))
    user_msg['To'] = user_email
    user_msg['Reply-To'] = admin_email
    user_msg['Message-ID'] = make_msgid(domain='automan.solutions')
    user_msg['Return-Path'] = sender

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(sender, email_password)
            server.sendmail(sender, admin_email, admin_msg.as_string())
            server.sendmail(sender, user_email, user_msg.as_string())
        return jsonify({'status': 'success', 'message': 'Emails sent successfully.'}), 200

    except smtplib.SMTPAuthenticationError:
        logging.error("SMTP Authentication failed.")
        return jsonify({'status': 'error', 'message': 'Email authentication failed.'}), 401

    except smtplib.SMTPRecipientsRefused:
        logging.error("Email recipient refused.")
        return jsonify({'status': 'error', 'message': 'Email recipient refused.'}), 400

    except smtplib.SMTPException as e:
        logging.error(f"SMTP error occurred: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to send emails due to server error.'}), 502

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return jsonify({'status': 'error', 'message': 'Internal server error.'}), 500


if __name__ == '__main__':
    env = os.getenv('FLASK_ENV', 'development')
    debug_mode = env != 'production'
    app.run(debug=debug_mode)
