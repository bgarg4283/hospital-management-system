from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def doctor_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_doctor():
            messages.error(request, "Access denied. Doctors only.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def patient_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_patient():
            messages.error(request, "Access denied. Patients only.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
