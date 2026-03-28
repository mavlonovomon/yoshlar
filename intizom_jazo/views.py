from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render

from .forms import DisciplineActionForm
from .models import DisciplineAction
from core.view_helpers import apply_sorting, normalize_sort_params


def _can_manage(user):
    return (
        getattr(user, 'is_site_admin', False)
    )


@login_required
def list_create(request):
    can_manage = _can_manage(request.user)

    if request.method == 'POST':
        if not can_manage:
            messages.error(request, "Intizomiy jazo qo'shish faqat admin yoki rahbar uchun.")
            return redirect('intizom_jazo:list')
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

    sort_field, sort_direction = normalize_sort_params(
        request,
        {'action_date', 'employee', 'action_type', 'status', 'end_date', 'resolved_date', 'reason', 'created_by'},
        'action_date',
        'desc',
    )
    sort_map = {
        'action_date': 'action_date',
        'employee': 'employee__full_name',
        'action_type': 'action_type',
        'status': 'status',
        'end_date': 'end_date',
        'resolved_date': 'resolved_date',
        'reason': 'reason',
        'created_by': 'created_by__full_name',
    }
    items = apply_sorting(items, sort_field, sort_direction, sort_map, 'action_date')

    context = {
        'form': form,
        'items': items,
        'q': q,
        'action_type': action_type,
        'action_choices': DisciplineAction.ACTION_CHOICES,
        'can_manage': can_manage,
        'sort_field': sort_field,
        'sort_direction': sort_direction,
    }
    return render(request, 'intizom_jazo/list.html', context)
