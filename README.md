# Hospital Management System (HMS)

A Django-based hospital management web application with doctor availability scheduling, patient appointment booking, Google Calendar integration, and a Node.js email notification service.

---

## Setup and Run

### Prerequisites

- Python 3.11+
- PostgreSQL (running locally)
- Node.js (any version)
- A Google Cloud project with Calendar API enabled (optional)
- Gmail account with App Password (optional)

---

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd hms-project
```

---

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

---

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Create the PostgreSQL database

```bash
psql -U postgres -c "CREATE DATABASE hms_db;"
```

---

### 5. Configure settings.py

Open `hms/hms/settings.py` and update the following sections directly:

**Database:**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'hms_db',
        'USER': 'postgres',
        'PASSWORD': 'your_postgres_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

**Email service URL:**
```python
EMAIL_SERVICE_URL = 'http://localhost:3000/email'
```

**Google Calendar (optional):**
```python
GOOGLE_CLIENT_ID = 'your_google_client_id'
GOOGLE_CLIENT_SECRET = 'your_google_client_secret'
GOOGLE_REDIRECT_URI = 'http://localhost:8000/accounts/google/callback/'
```

---

### 6. Create static folder

```bash
# Windows
mkdir hms\static

# Mac/Linux
mkdir -p hms/static
```

---

### 7. Run migrations

```bash
cd hms
python manage.py makemigrations accounts
python manage.py makemigrations appointments
python manage.py makemigrations notifications
python manage.py migrate
```

---

### 8. Create superuser (optional — for admin panel)

```bash
python manage.py createsuperuser
```

---

### 9. Start the Django server

```bash
python manage.py runserver
```

App is live at **http://localhost:8000**

---

### 10. Set up the email service (second terminal)

Open `email-service/server.js` and update credentials:

```javascript
const SMTP_USER = 'your_gmail@gmail.com'
const SMTP_PASSWORD = 'your_16char_app_password'
```

> **Gmail App Password:** Go to https://myaccount.google.com/apppasswords — enable 2FA first, then generate an App Password for HMS.

Install dependencies and run:

```bash
cd email-service
npm install nodemailer
node server.js
```

Email service is live at **http://localhost:3000/email**

---

### 11. Google Calendar setup (optional)

1. Go to https://console.cloud.google.com/
2. Create a project → Enable **Google Calendar API**
3. Create OAuth2 credentials (Web Application)
4. Add redirect URI: `http://localhost:8000/accounts/google/callback/`
5. Copy Client ID and Secret into `settings.py`
6. Add your Gmail as a Test User in OAuth consent screen
7. After login, click **Connect Google Calendar** in the navbar

---

### Running the full system

| Terminal 1 | Terminal 2 |
|---|---|
| `cd hms && python manage.py runserver` | `cd email-service && node server.js` |
| Django on **http://localhost:8000** | Email service on **http://localhost:3000** |

---

### Test the email service

**Windows PowerShell:**
```powershell
Invoke-WebRequest -Uri "http://localhost:3000/email" -Method POST -ContentType "application/json" -Body '{"trigger":"SIGNUP_WELCOME","payload":{"email":"your_gmail@gmail.com","name":"Test","role":"patient"}}'
```

**Mac/Linux:**
```bash
curl -X POST http://localhost:3000/email \
  -H "Content-Type: application/json" \
  -d '{"trigger":"SIGNUP_WELCOME","payload":{"email":"your@gmail.com","name":"Test","role":"patient"}}'
```

---

## System Architecture

### How the components connect

```
Browser
  │
  ▼
Django HMS (port 8000)
  │  session-based auth, PostgreSQL via Django ORM
  │
  ├──► PostgreSQL (hms_db)
  │      Users, AvailabilitySlots, Bookings
  │
  ├──► Node.js Email Service (port 3000) — HTTP POST
  │      server.js handles SIGNUP_WELCOME and BOOKING_CONFIRMATION
  │      sends email via Gmail SMTP (nodemailer)
  │
  └──► Google Calendar API (HTTPS)
         creates events for doctor and patient on booking confirmation
```

### Data model

**User** (custom `AbstractUser`): stores `role` (doctor | patient), email as login username, Google OAuth2 tokens (access token, refresh token, expiry).

**DoctorProfile / PatientProfile**: one-to-one extensions of User for role-specific fields (specialization, phone).

**AvailabilitySlot**: belongs to a doctor. Fields: `date`, `start_time`, `end_time`, `is_booked`. Unique constraint on `(doctor, date, start_time)` prevents duplicate slots at the DB level.

**Booking**: one-to-one with AvailabilitySlot (enforces one booking per slot at the schema level). Belongs to a patient. Stores Google Calendar event IDs for both doctor and patient.

### Role-based access

Enforced via two decorators in `accounts/decorators.py`:

- `@doctor_required` — checks `request.user.role == 'doctor'`, redirects with error message if not
- `@patient_required` — same check for patient role

Applied at the view level. Patients cannot reach slot creation or deletion endpoints. Doctors cannot reach the booking endpoint. The admin panel is separate and superuser-only.

### Google Calendar integration

OAuth2 tokens (access + refresh) are stored on the User model row. On every calendar API call, `notifications/gcal.py` checks token expiry and refreshes proactively 5 minutes before expiry using the stored refresh token. Calendar events are created after a booking is committed to the database. Calendar failure is logged server-side and never shown to the user as an error — it does not block the booking flow.

### Email notification service

A standalone Node.js HTTP server (`email-service/server.js`) listens on port 3000. The Django backend POSTs to it after signup and after booking confirmation. The service sends emails via Gmail SMTP using nodemailer. Email failures are logged and never raise exceptions in Django — email failure never blocks signup or booking.

---

## The Design Decision

### Race condition in slot booking: pessimistic vs optimistic locking

**The problem:** Two patients can load the same available slot page simultaneously and both click "Book" within milliseconds. Without coordination, both requests read `is_booked=False`, both proceed, and the same slot ends up with two bookings.

**Option A — Optimistic locking (version field + retry)**

Add a `version` integer to `AvailabilitySlot`. On update, include `WHERE version = <read_version>` in the query. If zero rows are updated, someone else got there first — retry or return a conflict error. This avoids holding DB locks and scales better under high concurrent read traffic.

**Option B — Pessimistic locking (`SELECT FOR UPDATE`)**

Wrap the booking in `transaction.atomic()` and acquire a row-level lock with `select_for_update()` before reading `is_booked`. PostgreSQL holds the lock until the transaction commits. The second concurrent request blocks at the lock until the first finishes, then reads `is_booked=True` and aborts cleanly.

**What I chose: Option B — pessimistic locking.**

For a clinic booking system, simultaneous contention on a single slot is the rare case, not the common case. The cost of a pessimistic lock — blocking one concurrent request for a few milliseconds — is negligible in practice. In exchange, we get a DB-level guarantee with zero retry logic in application code. Optimistic locking requires handling the retry loop (how many retries? what backoff?) and surfaces a "please try again" error to the user — a confusing UX path that pessimistic locking avoids entirely.

The `OneToOneField` on `Booking.slot` is a second layer of defense: even if the lock logic somehow failed, the DB unique constraint prevents two bookings for the same slot from ever being committed.

Pessimistic locking would become a bottleneck at very high concurrent slot contention — but for a local hospital system, that is not the failure mode to optimize for.

---

## Limitations

**What would break in production, and what I would fix first:**

1. **Google OAuth tokens stored in plaintext.** Access and refresh tokens sit in plain DB columns. In production these must be encrypted at rest using Django's `encrypted-model-fields` or a secrets manager. Fix this first — tokens are long-lived credentials.

2. **Email is synchronous and blocking.** The Node.js email call happens inside the Django request/response cycle. A slow or unavailable email service adds latency to signup and booking. In production, push notifications into a task queue (Celery + Redis) and process them asynchronously.

3. **No HTTPS.** Session cookies are transmitted over HTTP in development. In production: HTTPS only, `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`.

4. **SECRET_KEY is hardcoded.** Must be rotated and loaded from an environment variable or secrets manager before any internet-facing deployment.

5. **`select_for_update()` requires a multi-worker setup to demonstrate.** Django's dev server is single-threaded. To exercise the race condition protection under real load, you need gunicorn with multiple workers and a connection pooler like PgBouncer. The locking logic is correct — the dev environment just cannot simulate true concurrency.

6. **No multi-account Google Calendar support.** The model assumes one Google account per user. A doctor using a personal and work calendar would require a separate `OAuthToken` table keyed by user + provider + scope.