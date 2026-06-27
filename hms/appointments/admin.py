from django.contrib import admin
from .models import AvailabilitySlot, Booking


@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'date', 'start_time', 'end_time', 'is_booked']
    list_filter = ['is_booked', 'date']
    search_fields = ['doctor__email', 'doctor__first_name', 'doctor__last_name']


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['pk', 'patient', 'slot', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['patient__email']
