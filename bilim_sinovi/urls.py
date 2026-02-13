from django.urls import path
from .views import (
    TestConfigCreateView,
    TestConfigUpdateView,
    TestDetailView,
    TestListView,
    TestManageListView,
    TestResultsDashboardView,
    TestResultView,
    TestStartView,
)

app_name = 'bilim_sinovi'

urlpatterns = [
    path('', TestListView.as_view(), name='test_list'),
    path('manage/', TestManageListView.as_view(), name='test_manage_list'),
    path('manage/results/', TestResultsDashboardView.as_view(), name='test_results_dashboard'),
    path('manage/create/', TestConfigCreateView.as_view(), name='test_manage_create'),
    path('manage/<int:pk>/edit/', TestConfigUpdateView.as_view(), name='test_manage_edit'),
    path('start/<int:pk>/', TestStartView.as_view(), name='test_start'),
    path('take/<int:pk>/', TestDetailView.as_view(), name='test_detail'),
    path('result/<int:pk>/', TestResultView.as_view(), name='test_result'),
]
