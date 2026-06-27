from django import forms
from .models import AvailabilitySlot
from django.utils import timezone


class AvailabilitySlotForm(forms.ModelForm):
    class Meta:
        model = AvailabilitySlot
        fields = ['date', 'start_time', 'end_time']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }

    def clean(self):
        cleaned = super().clean()
        date = cleaned.get('date')
        start = cleaned.get('start_time')
        end = cleaned.get('end_time')

        if date and date < timezone.now().date():
            raise forms.ValidationError("Slot date must be in the future.")
        if start and end and start >= end:
            raise forms.ValidationError("End time must be after start time.")
        return cleaned
