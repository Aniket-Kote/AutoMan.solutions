import os
import logging
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
import json
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

app = Flask(__name__)

# Enable CORS for the /send_email endpoint only, adjust origins as needed
CORS(app)

# Configure logging for production
logging.basicConfig(level=logging.INFO)

def sanitize_input(text):
    return str(text).replace('\n', ' ').replace('\r', ' ').strip()

@app.before_request
def enforce_https():
    if not request.is_secure and os.getenv('FLASK_ENV') == 'production':
        abort(403, "HTTPS is required.")

@app.route('/send_email', methods=['POST'])
def send_email():
    sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
    if not sendgrid_api_key:
        logging.error("SENDGRID_API_KEY environment variable is not set.")
        return jsonify({'status': 'error', 'message': 'Server configuration error.'}), 500

    try:
        data = request.get_json(force=True, silent=False)
    except (TypeError, json.JSONDecodeError) as e:
        return jsonify({'status': 'error', 'message': f'Invalid JSON: {str(e)}'}), 400

    # Required
    user_email = data.get('user_email')
    if not user_email:
        return jsonify({'status': 'error', 'message': 'Missing required field: user_email'}), 400

    # Optional fields with defaults
    user_name = sanitize_input(data.get('user_name', 'User'))
    user_company_name = sanitize_input(data.get('user_company_name', 'N/A'))
    message = sanitize_input(data.get('message', ''))
    admin_subject = sanitize_input(data.get('admin_subject', f"New Inquiry from {user_name}"))
    user_subject = sanitize_input(data.get('user_subject', "Thank you for contacting Automan Solutions"))

    sender = "contact@automan.solutions"   # your verified SendGrid sender
    admin_email = sender

    # Compose admin email
    admin_body = (
        f"Details submitted by user:\n\n"
        f"Name: {user_name}\n"
        f"Email: {user_email}\n"
        f"Company: {user_company_name}\n"
        f"Requirement:\n{message}"
    )

    # Compose user confirmation email
    user_body = (
        f"Hi {user_name},\n\n"
        "Thanks for reaching out. We have received your details and will get back to you shortly.\n\n"
        "Best regards,\n"
        "Automan Solutions Team"
    )

    try:
        sg = SendGridAPIClient(sendgrid_api_key)

        # Send to admin
        admin_mail = Mail(
            from_email=Email(sender, "Automan Solutions"),
            to_emails=To(admin_email),
            subject=admin_subject,
            plain_text_content=Content("text/plain", admin_body)
        )
        sg.send(admin_mail)

        # Send confirmation to user
        user_mail = Mail(
            from_email=Email(sender, "Automan Solutions"),
            to_emails=To(user_email),
            subject=user_subject,
            plain_text_content=Content("text/plain", user_body)
        )
        sg.send(user_mail)

        return jsonify({'status': 'success', 'message': 'Emails sent successfully.'}), 200

    except Exception as e:
        logging.error(f"SendGrid error: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to send emails.'}), 500


if __name__ == '__main__':
    env = os.getenv('FLASK_ENV', 'development')
    debug_mode = env != 'production'
    app.run(debug=debug_mode)
