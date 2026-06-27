import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .forms import SignupForm, LoginForm
from .models import User
from notifications.tasks import send_email_notification


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            # Fire welcome email (non-blocking — errors are logged, not raised)
            send_email_notification('SIGNUP_WELCOME', {
                'email': user.email,
                'name': user.get_full_name() or user.email,
                'role': user.role,
            })
            messages.success(request, f"Welcome, {user.get_full_name() or user.email}!")
            return redirect('dashboard')
    else:
        form = SignupForm()
    return render(request, 'accounts/signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid email or password.")
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard_view(request):
    if request.user.is_doctor():
        return redirect('doctor_dashboard')
    return redirect('patient_dashboard')


# ── Google Calendar OAuth2 ──────────────────────────────────────────────────

def google_oauth_start(request):
    """Redirect the user to Google's OAuth2 consent screen."""
    if not request.user.is_authenticated:
        return redirect('login')

    params = urllib.parse.urlencode({
        'client_id': settings.GOOGLE_CLIENT_ID,
        'redirect_uri': settings.GOOGLE_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'https://www.googleapis.com/auth/calendar.events',
        'access_type': 'offline',
        'prompt': 'consent',
    })
    return redirect(f'https://accounts.google.com/o/oauth2/v2/auth?{params}')


def google_oauth_callback(request):
    """Exchange the auth code for tokens and store them on the user."""
    if not request.user.is_authenticated:
        return redirect('login')

    code = request.GET.get('code')
    if not code:
        messages.error(request, "Google authorization failed.")
        return redirect('dashboard')

    token_data = urllib.parse.urlencode({
        'code': code,
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'redirect_uri': settings.GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code',
    }).encode()

    try:
        req = urllib.request.Request(
            'https://oauth2.googleapis.com/token',
            data=token_data,
            method='POST',
        )
        with urllib.request.urlopen(req) as resp:
            tokens = json.loads(resp.read())

        user = request.user
        user.google_access_token = tokens.get('access_token')
        if 'refresh_token' in tokens:
            user.google_refresh_token = tokens['refresh_token']
        if 'expires_in' in tokens:
            from datetime import timedelta
            user.google_token_expiry = datetime.now(timezone.utc) + timedelta(seconds=tokens['expires_in'])
        user.save(update_fields=['google_access_token', 'google_refresh_token', 'google_token_expiry'])
        messages.success(request, "Google Calendar connected!")
    except Exception as e:
        messages.error(request, f"Failed to connect Google Calendar: {e}")

    return redirect('dashboard')
