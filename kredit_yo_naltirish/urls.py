from django.urls import path
from . import views

app_name = 'kredit_yo_naltirish'

urlpatterns = [
    path('', views.index, name='index'),
]
