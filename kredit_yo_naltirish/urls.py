from django.urls import path
from . import views

app_name = 'kredit_yo_naltirish'

urlpatterns = [
    path('', views.index, name='index'),
    path('svod/', views.svod, name='svod'),
    path('svod/export/', views.svod_export, name='svod_export'),
    path('add/', views.add_candidate, name='add_candidate'),
    path('search-yosh/', views.search_yosh, name='search_yosh'),
    path('process/<int:pk>/', views.move_to_process, name='move_to_process'),
    path('approve/<int:pk>/', views.approve_candidate, name='approve_candidate'),
    path('reject/<int:pk>/', views.reject_candidate, name='reject_candidate'),
    path('monitoring/enable/<int:pk>/', views.enable_monitoring, name='monitoring_enable'),
    path('monitoring/add/<int:pk>/', views.add_monitoring, name='monitoring_add'),
]
