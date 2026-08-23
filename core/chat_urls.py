"""Chat URLlari."""
from django.urls import path
from . import chat_views

app_name = 'chat'

urlpatterns = [
    path('api/contacts/', chat_views.contacts, name='contacts'),
    path('api/messages/<int:user_id>/', chat_views.messages, name='messages'),
    path('api/read/<int:user_id>/', chat_views.read_messages, name='read'),
    path('api/heartbeat/', chat_views.heartbeat, name='heartbeat'),
    path('api/unread-count/', chat_views.unread_count, name='unread_count'),
]
