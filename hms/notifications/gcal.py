"""
Google Calendar integration.

Design decision: tokens are stored encrypted-at-rest in the DB (User model)
rather than in a separate OAuth token store (e.g. django-allauth or a
dedicated OAuth2Session table).

Rationale: keeping tokens on the User row eliminates a join on every calendar
call and simplifies the data model for a single-Google-account-per-user
assumption stated in the task. The trade-off is that rotating encryption keys
requires a data migration, and multi-account support would require a separate
table. Both are acceptable limitations for the local demo scope.
"""

import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta, date, time

from django.conf import settings

logger = logging.getLogger(__name__)


def _refresh_access_token(user) -> bool:
    """Use the stored refresh token to get a new access token."""
    if not user.google_refresh_token:
        return False

    data = urllib.parse.urlencode({
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'refresh_token': user.google_refresh_token,
        'grant_type': 'refresh_token',
    }).encode()

    try:
        req = urllib.request.Request(
            'https://oauth2.googleapis.com/token',
            data=data,
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            tokens = json.loads(resp.read())

        user.google_access_token = tokens['access_token']
        user.google_token_expiry = datetime.now(timezone.utc) + timedelta(seconds=tokens.get('expires_in', 3600))
        user.save(update_fields=['google_access_token', 'google_token_expiry'])
        return True
    except Exception as e:
        logger.error("Failed to refresh Google token for user %s: %s", user.email, e)
        return False


def _get_valid_token(user) -> str | None:
    """Return a valid access token, refreshing if expired."""
    if not user.google_access_token:
        return None

    expiry = user.google_token_expiry
    if expiry and datetime.now(timezone.utc) >= expiry - timedelta(minutes=5):
        if not _refresh_access_token(user):
            return None

    return user.google_access_token


def create_calendar_event(
    user,
    title: str,
    date: date,
    start_time: time,
    end_time: time,
    description: str = '',
) -> str | None:
    """
    Create a Google Calendar event for the given user.

    Returns the event ID on success, None on failure.
    """
    token = _get_valid_token(user)
    if not token:
        logger.info("No valid Google token for user %s — skipping calendar event.", user.email)
        return None

    # Build RFC3339 datetime strings (assume UTC; adjust if you add TZ support)
    start_dt = datetime.combine(date, start_time).replace(tzinfo=timezone.utc).isoformat()
    end_dt = datetime.combine(date, end_time).replace(tzinfo=timezone.utc).isoformat()

    event_body = json.dumps({
        'summary': title,
        'description': description,
        'start': {'dateTime': start_dt, 'timeZone': 'UTC'},
        'end': {'dateTime': end_dt, 'timeZone': 'UTC'},
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://www.googleapis.com/calendar/v3/calendars/primary/events',
        data=event_body,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            event = json.loads(resp.read())
            event_id = event.get('id')
            logger.info("Created Google Calendar event %s for user %s", event_id, user.email)
            return event_id
    except urllib.error.HTTPError as e:
        logger.error("Google Calendar API error for user %s: %s %s", user.email, e.code, e.read())
        return None
    except Exception as e:
        logger.error("Failed to create calendar event for user %s: %s", user.email, e)
        return None
