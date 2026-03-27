from django.urls import path
from . import views

app_name = 'reyd'

urlpatterns = [
    path('', views.RaidEventListView.as_view(), name='index'),
    path('list/', views.RaidEventListView.as_view(), name='list'),
    path('create/', views.RaidEventCreateView.as_view(), name='create'),
    path('edit/<int:pk>/', views.RaidEventUpdateView.as_view(), name='edit'),
    path('detail/<int:pk>/', views.RaidEventDetailView.as_view(), name='detail'),
]
