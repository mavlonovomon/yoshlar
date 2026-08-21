from django.urls import path
from django.shortcuts import redirect
from . import views

app_name = 'ishsiz_yoshlar'

urlpatterns = [
    # Asosiy sahifalar -> 2026 ga redirect
    path('', lambda r: redirect('ishsiz_yoshlar:year_list', year=2026), name='index'),
    path('list/', lambda r: redirect('ishsiz_yoshlar:year_list', year=2026), name='list'),
    path('svod/', lambda r: redirect('ishsiz_yoshlar:year_svod', year=2026), name='svod'),

    # Yil bo'yicha sahifalar
    path('<int:year>/', views.UnemployedYouthListView.as_view(), name='year_list'),
    path('<int:year>/svod/', views.SvodTabsView.as_view(), name='year_svod'),
    path('<int:year>/export-mahalla-svod/', views.ExportMahallaSvodView.as_view(), name='year_export_mahalla_svod'),
    path('<int:year>/export-leader-svod/', views.ExportLeaderSvodView.as_view(), name='year_export_leader_svod'),
    path('<int:year>/export-professional-svod/', views.ExportProfessionalSvodView.as_view(), name='year_export_professional_svod'),

    # Boshqa sahifalar
    path('detailed-svod/', views.DetailedSvodView.as_view(), name='detailed_svod'),
    path('professional-svod/', lambda r: redirect('ishsiz_yoshlar:year_svod', year=2026), name='professional_svod'),
    path('export-professional-svod/', views.ExportProfessionalSvodView.as_view(), name='export_professional_svod'),
    path('export-mahalla-svod/', views.ExportMahallaSvodView.as_view(), name='export_mahalla_svod'),
    path('export-leader-svod/', views.ExportLeaderSvodView.as_view(), name='export_leader_svod'),
    path('leader-svod/', lambda r: redirect('ishsiz_yoshlar:year_svod', year=2026), name='leader_svod'),
    path('detail/<int:pk>/', views.UnemployedYouthDetailView.as_view(), name='detail'),
    path('detail/<int:pk>/pdf/', views.UnemployedYouthPDFView.as_view(), name='youth_pdf'),
    path('meeting-create/<int:pk>/', views.MeetingCreateView.as_view(), name='meeting_create'),
    path('assistance-update/<int:pk>/', views.AssistanceUpdateView.as_view(), name='assistance_update'),
    path('yosh-autocomplete/', views.YoshAutocompleteView.as_view(), name='yosh_autocomplete'),
    path('create/', views.UnemployedYouthCreateView.as_view(), name='create'),
    path('edit/<int:pk>/', views.UnemployedYouthUpdateView.as_view(), name='edit'),
    path('delete/<int:pk>/', views.UnemployedYouthDeleteView.as_view(), name='delete'),
    path('meeting-update/<int:pk>/', views.MeetingUpdateView.as_view(), name='meeting_update'),

    # Task Management URLs (Topshiriq Tizimi)
    path('tasks/', views.TaskListView.as_view(), name='task_list'),
    path('tasks/create/', views.TaskCreateView.as_view(), name='task_create'),
    path('tasks/<int:pk>/', views.TaskDetailView.as_view(), name='task_detail'),
    path('tasks/<int:pk>/edit/', views.TaskUpdateView.as_view(), name='task_edit'),
    path('tasks/<int:pk>/delete/', views.TaskDeleteView.as_view(), name='task_delete'),
    path('tasks/<int:pk>/respond/', views.TaskResponseCreateView.as_view(), name='task_respond'),
    path('tasks/<int:pk>/accept/', views.TaskAcceptView.as_view(), name='task_accept'),
    path('tasks/<int:pk>/review/', views.TaskReviewView.as_view(), name='task_review'),

    # Notifications URLs
    path('notifications/', views.NotificationListView.as_view(), name='notification_list'),
    path('notifications/<int:pk>/read/', views.MarkNotificationReadView.as_view(), name='notification_read'),
]
