from django.urls import path
from . import views

app_name = 'sorovnoma'

urlpatterns = [
    path('', views.survey_list, name='survey_list'),
    path('<int:pk>/responses/', views.survey_response_list, name='survey_response_list'),
    path('response/<int:pk>/', views.survey_response_detail, name='survey_response_detail'),
    path('response/<int:pk>/edit/', views.survey_response_edit, name='survey_response_edit'),
    path('<int:pk>/export/', views.export_survey_responses, name='export_survey_responses'),
    path('<int:pk>/fill/', views.survey_fill, name='survey_fill'),
    path('<int:pk>/status/<str:status>/', views.survey_status_change, name='survey_status_change'),
]
