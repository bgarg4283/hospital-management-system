import json
import logging
import urllib.request
import urllib.error

from django.conf import settings

logger = logging.getLogger(__name__)


def send_email_notification(trigger: str, payload: dict) -> bool:
    """
    POST to the local serverless email function.

    trigger: 'SIGNUP_WELCOME' | 'BOOKING_CONFIRMATION'
    payload: dict with email, name, and any trigger-specific fields

    Returns True on success, False on any error.
    Errors are logged but never raised — email failure must never break the main flow.
    """
    body = json.dumps({'trigger': trigger, 'payload': payload}).encode('utf-8')
    req = urllib.request.Request(
        settings.EMAIL_SERVICE_URL,
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
            if status == 200:
                logger.info("Email notification sent: trigger=%s email=%s", trigger, payload.get('email'))
                return True
            else:
                logger.warning("Email service returned %s for trigger=%s", status, trigger)
                return False
    except urllib.error.URLError as e:
        logger.warning("Email service unreachable (trigger=%s): %s", trigger, e)
        return False
    except Exception as e:
        logger.error("Unexpected error calling email service (trigger=%s): %s", trigger, e)
        return False
