"""
Serverless email notification handler.

Supports two triggers:
  - SIGNUP_WELCOME       — sent when a new user signs up
  - BOOKING_CONFIRMATION — sent when a patient books a slot

Invoked via HTTP POST from the Django HMS backend.
Runs locally via: serverless offline
"""

import json
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', SMTP_USER)


def _send_email(to: str, subject: str, html_body: str, text_body: str) -> bool:
    """Send a single email via SMTP. Returns True on success."""
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not set — email not sent to %s", to)
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = FROM_EMAIL
    msg['To'] = to
    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, [to], msg.as_string())
        logger.info("Email sent to %s | subject: %s", to, subject)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to, e)
        return False


# ── Template builders ────────────────────────────────────────────────────────

def _build_welcome_email(payload: dict) -> tuple[str, str, str]:
    name = payload.get('name', 'User')
    role = payload.get('role', 'user').capitalize()
    subject = f"Welcome to HMS, {name}!"
    html = f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:auto">
      <div style="background:#1a3c5e;padding:24px;border-radius:8px 8px 0 0">
        <h2 style="color:#fff;margin:0">🏥 Welcome to HMS</h2>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #e0e0e0;border-radius:0 0 8px 8px">
        <p>Hi <strong>{name}</strong>,</p>
        <p>Your <strong>{role}</strong> account has been created successfully.</p>
        <p>You can now log in and start using the Hospital Management System.</p>
        <a href="http://localhost:8000/accounts/login/"
           style="display:inline-block;background:#1a3c5e;color:#fff;padding:10px 20px;
                  border-radius:6px;text-decoration:none;margin-top:12px">
          Go to Dashboard
        </a>
        <p style="margin-top:24px;color:#888;font-size:12px">
          This is an automated message from HMS. Please do not reply.
        </p>
      </div>
    </body></html>
    """
    text = f"Hi {name},\n\nWelcome to HMS! Your {role} account is ready.\nLogin at http://localhost:8000/accounts/login/"
    return subject, html, text


def _build_booking_email(payload: dict) -> tuple[str, str, str]:
    patient = payload.get('patient_name', 'Patient')
    doctor = payload.get('doctor_name', 'Doctor')
    date = payload.get('date', '')
    start = payload.get('start_time', '')
    end = payload.get('end_time', '')
    subject = f"Appointment Confirmed — {date} at {start}"
    html = f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:auto">
      <div style="background:#1a3c5e;padding:24px;border-radius:8px 8px 0 0">
        <h2 style="color:#fff;margin:0">✅ Appointment Confirmed</h2>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #e0e0e0;border-radius:0 0 8px 8px">
        <p>Hi <strong>{patient}</strong>,</p>
        <p>Your appointment has been confirmed:</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
          <tr style="background:#f5f7fa">
            <td style="padding:10px;font-weight:bold">Doctor</td>
            <td style="padding:10px">Dr. {doctor}</td>
          </tr>
          <tr>
            <td style="padding:10px;font-weight:bold">Date</td>
            <td style="padding:10px">{date}</td>
          </tr>
          <tr style="background:#f5f7fa">
            <td style="padding:10px;font-weight:bold">Time</td>
            <td style="padding:10px">{start} – {end}</td>
          </tr>
        </table>
        <p style="color:#888;font-size:12px">This is an automated message from HMS.</p>
      </div>
    </body></html>
    """
    text = f"Appointment confirmed!\nDoctor: Dr. {doctor}\nDate: {date}\nTime: {start}–{end}"
    return subject, html, text


# ── Lambda handler ────────────────────────────────────────────────────────────

def send_email(event, context):
    """
    HTTP POST handler invoked by the HMS Django backend.

    Expected body:
    {
        "trigger": "SIGNUP_WELCOME" | "BOOKING_CONFIRMATION",
        "payload": { ... trigger-specific fields ... }
    }
    """
    try:
        body = event.get('body') or '{}'
        if isinstance(body, str):
            body = json.loads(body)

        trigger = body.get('trigger')
        payload = body.get('payload', {})
        email_to = payload.get('email')

        if not trigger or not email_to:
            return _response(400, {'error': 'Missing trigger or email in payload'})

        logger.info("Processing trigger=%s for=%s", trigger, email_to)

        if trigger == 'SIGNUP_WELCOME':
            subject, html, text = _build_welcome_email(payload)
        elif trigger == 'BOOKING_CONFIRMATION':
            subject, html, text = _build_booking_email(payload)
        else:
            return _response(400, {'error': f'Unknown trigger: {trigger}'})

        success = _send_email(email_to, subject, html, text)

        if success:
            return _response(200, {'status': 'sent', 'trigger': trigger, 'to': email_to})
        else:
            # Return 200 even on SMTP failure so the Django side doesn't retry aggressively;
            # the error is logged on the serverless side.
            return _response(200, {'status': 'logged', 'note': 'SMTP credentials not configured or send failed'})

    except Exception as e:
        logger.error("Unhandled error in send_email: %s", e)
        return _response(500, {'error': str(e)})


def _response(status_code: int, body: dict) -> dict:
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(body),
    }
