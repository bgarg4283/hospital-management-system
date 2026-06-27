from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('google/', views.google_oauth_start, name='google_oauth_start'),
    path('google/callback/', views.google_oauth_callback, name='google_oauth_callback'),
]
