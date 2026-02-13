from django.urls import path
from . import views

app_name = 'beshtashabbus'

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('list/', views.FiveInitiativeListView.as_view(), name='list'),
    path('create/', views.FiveInitiativeCreateView.as_view(), name='create'),
    path('edit/<int:pk>/', views.FiveInitiativeUpdateView.as_view(), name='edit'),
    path('detail/<int:pk>/', views.FiveInitiativeDetailView.as_view(), name='detail'),
]
