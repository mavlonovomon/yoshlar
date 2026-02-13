from django.urls import path
from . import views

app_name = 'eimzo_auth'

urlpatterns = [
    path('eimzo/', views.eimzo_login_page, name='eimzo_login'),
    path('eimzo/challenge/', views.eimzo_challenge, name='eimzo_challenge'),
    path('eimzo/verify/', views.eimzo_verify, name='eimzo_verify'),
]
