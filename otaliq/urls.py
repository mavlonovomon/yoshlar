from django.urls import path
from . import views

app_name = 'otaliq'

urlpatterns = [
    path('', views.OtaliqListView.as_view(), name='index'),
    path('list/', views.OtaliqListView.as_view(), name='list'),
    path('detail/<int:pk>/', views.OtaliqDetailView.as_view(), name='detail'),
    path('detail/<int:pk>/pdf/', views.OtaliqYouthPDFView.as_view(), name='youth_pdf'),
    path('svod/', views.SvodView.as_view(), name='svod'),
    path('leaders/', views.OtaliqLeaderListView.as_view(), name='leader_list'),
    path('leaders/add/', views.OtaliqLeaderCreateView.as_view(), name='leader_add'),
]
