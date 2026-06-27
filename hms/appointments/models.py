from django.db import models
from django.conf import settings


class AvailabilitySlot(models.Model):
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='availability_slots',
        limit_choices_to={'role': 'doctor'},
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_booked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'start_time']
        # A doctor cannot have two slots with the same start time on the same day
        unique_together = [('doctor', 'date', 'start_time')]

    def __str__(self):
        status = 'booked' if self.is_booked else 'free'
        return f"Dr.{self.doctor.last_name} | {self.date} {self.start_time}–{self.end_time} [{status}]"


class Booking(models.Model):
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings',
        limit_choices_to={'role': 'patient'},
    )
    slot = models.OneToOneField(
        AvailabilitySlot,
        on_delete=models.CASCADE,
        related_name='booking',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CONFIRMED)
    created_at = models.DateTimeField(auto_now_add=True)

    # Google Calendar event IDs (stored after creation)
    patient_gcal_event_id = models.CharField(max_length=255, blank=True)
    doctor_gcal_event_id = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Booking #{self.pk}: {self.patient.email} → {self.slot}"
