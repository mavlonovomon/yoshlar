from django.urls import path
from . import views

app_name = 'intizom_jazo'

urlpatterns = [
    path('', views.list_create, name='list'),
]
