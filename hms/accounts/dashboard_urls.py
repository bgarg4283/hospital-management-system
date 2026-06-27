from django.urls import path
from appointments import views as appt_views

urlpatterns = [
    path('', appt_views.dashboard_redirect, name='dashboard'),
    path('doctor/', appt_views.doctor_dashboard, name='doctor_dashboard'),
    path('patient/', appt_views.patient_dashboard, name='patient_dashboard'),
]
