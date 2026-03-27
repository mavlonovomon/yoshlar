from django.urls import path
from . import views

app_name = 'beshtashabbus'

urlpatterns = [
    path('', views.FiveInitiativeListView.as_view(), name='index'),
    path('list/', views.FiveInitiativeListView.as_view(), name='list'),
    path('applications/upload/', views.FiveInitiativeApplicationUploadView.as_view(), name='application_upload'),
    path('applications/svod/', views.FiveInitiativeApplicationSvodView.as_view(), name='application_svod'),
    path('applications/svod-extended/', views.FiveInitiativeApplicationExtendedSvodView.as_view(), name='application_svod_extended'),
    path('applications/svod-norma/', views.FiveInitiativeSvodNormaView.as_view(), name='application_svod_norma'),
    path('applications/youth-list/', views.FiveInitiativeYouthListView.as_view(), name='application_youth_list'),
    path('applications/submit/', views.FiveInitiativeApplicationSubmitView.as_view(), name='application_submit'),
    path('applications/sporttypes/', views.FiveInitiativeSportTypesView.as_view(), name='application_sporttypes'),
    path('create/', views.FiveInitiativeCreateView.as_view(), name='create'),
    path('edit/<int:pk>/', views.FiveInitiativeUpdateView.as_view(), name='edit'),
    path('detail/<int:pk>/', views.FiveInitiativeDetailView.as_view(), name='detail'),
]
