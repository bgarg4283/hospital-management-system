# AI Tool Usage Log

## Tool: Claude (Anthropic)

**Session**: Full scaffold  
**Date**: 2026

### Prompt given to Claude:
> Serverless email service hospital management system per the task spec including:AvailabilitySlot and Booking models with SELECT FOR UPDATE race condition handling, Google Calendar OAuth2 integration, 

### What Claude generated:
- `hms/hms/settings.py` — Django settings with PostgreSQL, custom auth, email service URL, Google OAuth config
- `hms/accounts/models.py` — Custom User with role field and Google token storage, DoctorProfile, PatientProfile
- `hms/accounts/forms.py` — SignupForm, LoginForm (email-based auth)
- `hms/accounts/decorators.py` — `@doctor_required`, `@patient_required` decorators


### What I reviewed and modified:
- Verified the SELECT FOR UPDATE approach is correct for PostgreSQL
- Confirmed the OneToOne constraint on Booking.slot enforces the "one booking per slot" invariant at the DB level
- Adjusted the Google token refresh window to 5 minutes before expiry
- Confirmed email errors are swallowed (logged, not raised) so email failure never breaks the booking flow

### Lines I could not defend:
- None. All logic was reviewed before committing.
