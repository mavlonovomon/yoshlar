from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render

from .forms import DisciplineActionForm
from .models import DisciplineAction


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

    context = {
        'form': form,
        'items': items,
        'q': q,
        'action_type': action_type,
        'action_choices': DisciplineAction.ACTION_CHOICES,
        'can_manage': can_manage,
    }
    return render(request, 'intizom_jazo/list.html', context)
