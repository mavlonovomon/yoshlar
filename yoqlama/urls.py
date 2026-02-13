from django.urls import path
from . import views

app_name = 'yoqlama'

urlpatterns = [
    path('list/', views.AttendanceListView.as_view(), name='list'),
    path('create/', views.AttendanceCreateView.as_view(), name='create'),
    path('edit/<int:pk>/', views.AttendanceUpdateView.as_view(), name='edit'),
    path('detail/<int:pk>/', views.AttendanceDetailView.as_view(), name='detail'),
]
