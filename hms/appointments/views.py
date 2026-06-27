from datetime import datetime, timezone as dt_timezone

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import doctor_required, patient_required
from accounts.models import User
from notifications.tasks import send_email_notification
from notifications.gcal import create_calendar_event

from .forms import AvailabilitySlotForm
from .models import AvailabilitySlot, Booking


# ── Shared ─────────────────────────────────────────────────────────────────

@login_required
def dashboard_redirect(request):
    if request.user.is_doctor():
        return redirect('doctor_dashboard')
    return redirect('patient_dashboard')


# ── Doctor views ────────────────────────────────────────────────────────────

@doctor_required
def doctor_dashboard(request):
    slots = AvailabilitySlot.objects.filter(doctor=request.user).order_by('date', 'start_time')
    form = AvailabilitySlotForm()
    return render(request, 'appointments/doctor_dashboard.html', {
        'slots': slots,
        'form': form,
        'user': request.user,
    })


@doctor_required
def create_slot(request):
    if request.method == 'POST':
        form = AvailabilitySlotForm(request.POST)
        if form.is_valid():
            slot = form.save(commit=False)
            slot.doctor = request.user
            try:
                slot.save()
                messages.success(request, "Availability slot created.")
            except Exception:
                messages.error(request, "A slot with that date and start time already exists.")
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{field}: {err}")
    return redirect('doctor_dashboard')


@doctor_required
def delete_slot(request, slot_id):
    slot = get_object_or_404(AvailabilitySlot, pk=slot_id, doctor=request.user)
    if slot.is_booked:
        messages.error(request, "Cannot delete a booked slot.")
    else:
        slot.delete()
        messages.success(request, "Slot deleted.")
    return redirect('doctor_dashboard')


# ── Patient views ───────────────────────────────────────────────────────────

@patient_required
def patient_dashboard(request):
    doctors = User.objects.filter(role='doctor').select_related('doctor_profile')
    my_bookings = Booking.objects.filter(
        patient=request.user,
        status=Booking.STATUS_CONFIRMED,
    ).select_related('slot__doctor').order_by('slot__date', 'slot__start_time')
    return render(request, 'appointments/patient_dashboard.html', {
        'doctors': doctors,
        'my_bookings': my_bookings,
        'user': request.user,
    })


@patient_required
def doctor_slots(request, doctor_id):
    doctor = get_object_or_404(User, pk=doctor_id, role='doctor')
    now = timezone.now()
    slots = AvailabilitySlot.objects.filter(
        doctor=doctor,
        is_booked=False,
        date__gte=now.date(),
    ).exclude(
        # Exclude slots that are today but in the past
        Q(date=now.date()) & Q(start_time__lt=now.time())
    ).order_by('date', 'start_time')
    return render(request, 'appointments/doctor_slots.html', {
        'doctor': doctor,
        'slots': slots,
    })


@patient_required
def book_slot(request, slot_id):
    """
    Race-condition safe booking using SELECT FOR UPDATE inside a transaction.

    Design decision: we use SELECT FOR UPDATE (pessimistic lock) rather than
    optimistic concurrency (version field + retry). This guarantees exactly-once
    booking at the DB level without retries in application code, at the cost of
    slightly higher lock contention under load — an acceptable trade-off for a
    clinic booking system where simultaneous contention on a single slot is rare
    and the failure path (two patients booking at once) is unacceptable.
    """
    if request.method != 'POST':
        return redirect('patient_dashboard')

    try:
        with transaction.atomic():
            # Lock the row for the duration of this transaction
            slot = AvailabilitySlot.objects.select_for_update().get(pk=slot_id)

            if slot.is_booked:
                messages.error(request, "Sorry, that slot was just booked by someone else.")
                return redirect('patient_dashboard')

            if slot.doctor == request.user:
                messages.error(request, "You cannot book your own slot.")
                return redirect('patient_dashboard')

            slot.is_booked = True
            slot.save(update_fields=['is_booked'])

            booking = Booking.objects.create(patient=request.user, slot=slot)

        # Outside the transaction: async side-effects
        _post_booking_actions(booking)
        messages.success(request, f"Appointment booked with Dr. {slot.doctor.get_full_name()} on {slot.date} at {slot.start_time}.")

    except AvailabilitySlot.DoesNotExist:
        messages.error(request, "Slot not found.")

    return redirect('patient_dashboard')


def _post_booking_actions(booking: Booking):
    """Fire email notifications and Google Calendar events after a booking."""
    slot = booking.slot
    doctor = slot.doctor
    patient = booking.patient

    # Email notifications
    send_email_notification('BOOKING_CONFIRMATION', {
        'email': patient.email,
        'patient_name': patient.get_full_name() or patient.email,
        'doctor_name': doctor.get_full_name() or doctor.email,
        'date': str(slot.date),
        'start_time': str(slot.start_time),
        'end_time': str(slot.end_time),
    })

    # Google Calendar — patient calendar
    if patient.google_access_token:
        patient_event_id = create_calendar_event(
            user=patient,
            title=f"Appointment with Dr. {doctor.get_full_name()}",
            date=slot.date,
            start_time=slot.start_time,
            end_time=slot.end_time,
            description=f"Booked via HMS. Booking ID: {booking.pk}",
        )
        if patient_event_id:
            booking.patient_gcal_event_id = patient_event_id

    # Google Calendar — doctor calendar
    if doctor.google_access_token:
        doctor_event_id = create_calendar_event(
            user=doctor,
            title=f"Appointment with {patient.get_full_name()}",
            date=slot.date,
            start_time=slot.start_time,
            end_time=slot.end_time,
            description=f"Patient: {patient.email}. Booking ID: {booking.pk}",
        )
        if doctor_event_id:
            booking.doctor_gcal_event_id = doctor_event_id

    booking.save(update_fields=['patient_gcal_event_id', 'doctor_gcal_event_id'])
