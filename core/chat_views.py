"""Chat API viewlari."""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q, Max, Count
from .models import Chat, ChatMessage, ChatSession, User
import json


def _json_error(message, status=400):
    return JsonResponse({'error': message}, status=status)


@login_required
def contacts(request):
    """Barcha yetakchilar kontaktlar ro'yxati."""
    if request.method != 'GET':
        return _json_error('Faqat GET', 405)

    user = request.user
    now = timezone.now()

    # Barcha foydalanuvchilarni olish (o'zini talab qilmaymiz)
    all_users = User.objects.filter(is_active=True).exclude(pk=user.pk)

    # Mavjud chatlarni olish
    user_chats = {}
    for chat in Chat.objects.filter(Q(user1=user) | Q(user2=user)).annotate(
        last_msg_text=Max('messages__text'),
        last_msg_time=Max('messages__created_at'),
        unread=Count('messages', filter=Q(messages__read_at=None) & ~Q(messages__sender=user))
    ):
        contact_id = chat.user2_id if chat.user1_id == user.pk else chat.user1_id
        user_chats[contact_id] = {
            'last_message': chat.last_msg_text or '',
            'last_message_time': chat.last_msg_time.isoformat() if chat.last_msg_time else None,
            'unread_count': chat.unread,
        }

    # Online statuslarni to'plash
    online_users = {}
    for session in ChatSession.objects.filter(user__in=all_users):
        is_online = (now - session.last_seen).total_seconds() < 30
        if is_online:
            online_users[session.user_id] = True

    result = []
    for u in all_users:
        chat_data = user_chats.get(u.pk, {})
        result.append({
            'id': u.pk,
            'full_name': u.full_name or u.username,
            'profile_image': u.profile_image.url if u.profile_image else None,
            'last_message': chat_data.get('last_message', ''),
            'last_message_time': chat_data.get('last_message_time'),
            'unread_count': chat_data.get('unread_count', 0),
            'is_online': u.pk in online_users,
            'last_seen': None,
        })

    # Saralash: avval suhbat bo'lganlar (oxirgi xabar vaqti bo'yicha), keyin qolganlari
    result.sort(key=lambda x: x['last_message_time'] or '', reverse=True)

    return JsonResponse({'contacts': result})


@login_required
def messages(request, user_id):
    """Xabarlarni olish yoki yuborish."""
    try:
        contact = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return _json_error('Foydalanuvchi topilmadi', 404)

    chat = Chat.get_or_create_chat(request.user, contact)

    if request.method == 'GET':
        since = request.GET.get('since')
        qs = chat.messages.all()
        if since:
            qs = qs.filter(created_at__gt=since)

        result = []
        for msg in qs.select_related('sender'):
            result.append({
                'id': msg.pk,
                'sender_id': msg.sender_id,
                'text': msg.text,
                'created_at': msg.created_at.isoformat(),
                'read_at': msg.read_at.isoformat() if msg.read_at else None,
            })

        return JsonResponse({'messages': result, 'chat_id': chat.pk})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            text = data.get('text', '').strip()
        except (json.JSONDecodeError, AttributeError):
            return _json_error('Noto\'g\'ri format')

        if not text:
            return _json_error('Xabar bo\'sh bo\'lmasligi kerak')
        if len(text) > 2000:
            return _json_error('Xabar juda uzun (maks. 2000 belgi)')

        msg = ChatMessage.objects.create(
            chat=chat,
            sender=request.user,
            text=text
        )
        chat.save()  # updated_at yangilash

        return JsonResponse({
            'id': msg.pk,
            'text': msg.text,
            'created_at': msg.created_at.isoformat(),
        }, status=201)

    return _json_error('Noto\'g\'ri method', 405)


@login_required
def read_messages(request, user_id):
    """Xabarlarni o'qilgan deb belgilash."""
    if request.method != 'POST':
        return _json_error('Faqat POST', 405)

    try:
        contact = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return _json_error('Foydalanuvchi topilmadi', 404)

    chat = Chat.get_or_create_chat(request.user, contact)
    now = timezone.now()

    updated = ChatMessage.objects.filter(
        chat=chat,
        sender=contact,
        read_at=None
    ).update(read_at=now)

    return JsonResponse({'status': 'ok', 'updated': updated})


@login_required
def heartbeat(request):
    """Online status yangilash."""
    if request.method != 'POST':
        return _json_error('Faqat POST', 405)

    session, _ = ChatSession.objects.get_or_create(user=request.user)
    session.last_seen = timezone.now()
    session.save(update_fields=['last_seen'])

    return JsonResponse({'status': 'ok'})


@login_required
def unread_count(request):
    """Jami o'qilmagan xabar soni."""
    if request.method != 'GET':
        return _json_error('Faqat GET', 405)

    count = ChatMessage.objects.filter(
        chat__in=Chat.objects.filter(Q(user1=request.user) | Q(user2=request.user)),
        read_at=None
    ).exclude(sender=request.user).count()

    return JsonResponse({'count': count})
