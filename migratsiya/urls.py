from django.urls import path
from . import views

app_name = 'migratsiya'

urlpatterns = [
    path('', views.MigrationYouthListView.as_view(), name='index'),
    path('list/', views.MigrationYouthListView.as_view(), name='list'),
    path('create/', views.MigrationYouthCreateView.as_view(), name='create'),
    path('edit/<int:pk>/', views.MigrationYouthUpdateView.as_view(), name='edit'),
    path('detail/<int:pk>/', views.MigrationYouthDetailView.as_view(), name='detail'),
    path('meeting-create/<int:pk>/', views.MeetingCreateView.as_view(), name='meeting_create'),
]
