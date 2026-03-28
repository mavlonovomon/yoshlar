from django.urls import path
from . import views_auth
from . import views_mega
from . import views_kpi
from . import views_yosh

urlpatterns = [
    path('login/', views_auth.login_view, name='login'),
    path('login/oneid/', views_auth.login_oneid, name='login_oneid'),
    path('auth/oneid/callback/', views_auth.callback_oneid, name='callback_oneid'),
    path('logout/', views_auth.logout_view, name='logout'),
    path('kpi/', views_kpi.kpi_dashboard, name='kpi_dashboard'),
    path('', views_yosh.dashboard, name='dashboard'),
    path('dashboard/', views_yosh.dashboard, name='dashboard_alias'),
    path('yoshlar/', views_yosh.yosh_list, name='yosh_list'),
    path('yoshlar/maktab-oquvchilar/', views_yosh.maktab_oquvchi_list, name='maktab_oquvchi_list'),
    path('yoshlar/maktab-aniqlanmagan/', views_yosh.maktab_oquvchi_pending_list, name='maktab_oquvchi_pending_list'),
    path('yoshlar/maktab-aniqlanmagan/<int:pk>/assign/', views_yosh.maktab_oquvchi_assign, name='maktab_oquvchi_assign'),
    path('yoshlar/new/', views_yosh.yosh_detail, name='yosh_create'),
    path('yoshlar/<int:pk>/', views_yosh.yosh_detail, name='yosh_detail'),
    path('yoshlar/<int:pk>/refresh-photo/', views_yosh.yosh_refresh_photo, name='yosh_refresh_photo'),
    path('meeting/<int:pk>/edit/', views_yosh.meeting_edit, name='meeting_edit'),
    path('profile/', views_yosh.user_profile, name='user_profile'),
    path('users/', views_yosh.user_list, name='user_list'),
    path('info/', views_yosh.info_view, name='info'),
    path('mega-loyihalar/', views_mega.mega_projects, name='mega_projects'),
    path('mega-loyihalar/mutolaa/', views_mega.mega_mutolaa, name='mega_mutolaa'),
    path('mega-loyihalar/mutolaa/refresh/', views_mega.mega_mutolaa_refresh, name='mega_mutolaa_refresh'),
    path('mega-loyihalar/ustoz-ai/', views_mega.mega_ustoz_ai, name='mega_ustoz_ai'),
    path('mega-loyihalar/ustoz-ai/refresh/', views_mega.mega_ustoz_ai_refresh, name='mega_ustoz_ai_refresh'),
    path('mega-loyihalar/uzchess/', views_mega.mega_uzchess, name='mega_uzchess'),
    path('mega-loyihalar/uzchess/refresh/', views_mega.mega_uzchess_refresh, name='mega_uzchess_refresh'),
    path('mega-loyihalar/qizlar-akademiyasi/', views_mega.mega_girls_academy, name='mega_girls_academy'),
    path('mega-loyihalar/qizlar-akademiyasi/refresh/', views_mega.mega_girls_academy_refresh, name='mega_girls_academy_refresh'),
]
