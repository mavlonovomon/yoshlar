from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('kpi/', views.kpi_dashboard, name='kpi_dashboard'),
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard_alias'),
    path('yoshlar/', views.yosh_list, name='yosh_list'),
    path('yoshlar/new/', views.yosh_detail, name='yosh_create'),
    path('yoshlar/<int:pk>/', views.yosh_detail, name='yosh_detail'),
    path('meeting/<int:pk>/edit/', views.meeting_edit, name='meeting_edit'),
    path('profile/', views.user_profile, name='user_profile'),
    path('users/', views.user_list, name='user_list'),
    path('info/', views.info_view, name='info'),
    path('mega-loyihalar/', views.mega_projects, name='mega_projects'),
    path('mega-loyihalar/mutolaa/', views.mega_mutolaa, name='mega_mutolaa'),
    path('mega-loyihalar/mutolaa/refresh/', views.mega_mutolaa_refresh, name='mega_mutolaa_refresh'),
    path('mega-loyihalar/ustoz-ai/', views.mega_ustoz_ai, name='mega_ustoz_ai'),
    path('mega-loyihalar/ustoz-ai/refresh/', views.mega_ustoz_ai_refresh, name='mega_ustoz_ai_refresh'),
    path('mega-loyihalar/uzchess/', views.mega_uzchess, name='mega_uzchess'),
    path('mega-loyihalar/uzchess/refresh/', views.mega_uzchess_refresh, name='mega_uzchess_refresh'),
    path('mega-loyihalar/qizlar-akademiyasi/', views.mega_girls_academy, name='mega_girls_academy'),
    path('mega-loyihalar/qizlar-akademiyasi/refresh/', views.mega_girls_academy_refresh, name='mega_girls_academy_refresh'),
]
