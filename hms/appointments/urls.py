from django.urls import path
from . import views

urlpatterns = [
    path('slot/create/', views.create_slot, name='create_slot'),
    path('slot/<int:slot_id>/delete/', views.delete_slot, name='delete_slot'),
    path('doctor/<int:doctor_id>/slots/', views.doctor_slots, name='doctor_slots'),
    path('slot/<int:slot_id>/book/', views.book_slot, name='book_slot'),
]
