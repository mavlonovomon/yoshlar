from .models import TaskNotification


def task_notifications(request):
    """Add unread task notifications count to context"""
    context = {}
    
    if request.user.is_authenticated:
        context['unread_notifications'] = TaskNotification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()
    else:
        context['unread_notifications'] = 0
    
    return context
