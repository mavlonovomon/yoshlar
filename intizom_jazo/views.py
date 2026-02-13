from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render

from .forms import DisciplineActionForm
from .models import DisciplineAction


def _can_manage(user):
    return (
        user.is_superuser
        or getattr(user, 'role', '') in {'SUPER_ADMIN', 'RAHBAR'}
        or user.is_staff
        or getattr(user, 'is_sector_coordinator', False)
    )


@login_required
def list_create(request):
    if not _can_manage(request.user):
        messages.error(request, "Bu bo'lim faqat Super Admin yoki rahbar uchun.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = DisciplineActionForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, "Intizomiy jazo yozuvi saqlandi.")
            return redirect('intizom_jazo:list')
    else:
        form = DisciplineActionForm()

    q = (request.GET.get('q') or '').strip()
    action_type = (request.GET.get('action_type') or '').strip()

    items = DisciplineAction.objects.select_related('employee', 'created_by').all()
    if q:
        items = items.filter(
            Q(employee__full_name__icontains=q) |
            Q(employee__username__icontains=q) |
            Q(employee__pinfl__icontains=q)
        )
    if action_type:
        items = items.filter(action_type=action_type)

    context = {
        'form': form,
        'items': items,
        'q': q,
        'action_type': action_type,
        'action_choices': DisciplineAction.ACTION_CHOICES,
    }
    return render(request, 'intizom_jazo/list.html', context)
