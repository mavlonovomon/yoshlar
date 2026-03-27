import uuid

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.models import User
from .forms import TaskForm, TaskResponseForm
from .models import Task, TaskGroup, TaskNotification, TaskResponse


class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return (
            self.request.user.is_staff
            or self.request.user.is_superuser
            or getattr(self.request.user, 'role', None) == 'RAHBAR'
        )


# Task Management Views (Topshiriq Tizimi)
def create_task_notification(task, notification_type, recipient):
    """Helper function to create task notifications"""
    message_map = {
        'TASK_CREATED': f"Yangi topshiriq yaratildi: {task.title}",
        'TASK_UPDATED': f"Topshiriq yangilandi: {task.title}",
        'TASK_RESPONSE': f"{recipient.full_name} topshiriqqa javob berdi: {task.title}",
        'TASK_COMPLETED': f"Topshiriq yakunlandi: {task.title}",
        'TASK_OVERDUE': f"Topshiriq muddati o'tgan: {task.title}",
        'TASK_RETURNED': f"Topshiriq qaytarildi: {task.title}",
        'TASK_APPROVED': f"Topshiriq tasdiqlandi: {task.title}",
    }
    TaskNotification.objects.create(
        task=task,
        recipient=recipient,
        notification_type=notification_type,
        message=message_map.get(notification_type, '')
    )


class TaskListView(LoginRequiredMixin, ListView):
    model = Task
    template_name = 'ishsiz_yoshlar/task_list.html'
    context_object_name = 'tasks'
    page_size = 25
    paginate_by = None

    def get_queryset(self):
        user = self.request.user
        queryset = Task.objects.select_related(
            'assigned_to', 'created_by', 'target_youth', 'target_mahalla', 'task_group'
        ).all()
        
        # Filter: admins see all tasks, users see only their assigned tasks
        if not getattr(user, 'is_site_admin', False) and not user.is_staff:
            queryset = queryset.filter(assigned_to=user)
        else:
            assigned_to = self.request.GET.get('assigned_to')
            if assigned_to:
                queryset = queryset.filter(assigned_to_id=assigned_to)
        
        # Status filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Priority filter
        priority = self.request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        # Task title search (batch-friendly, handled in context grouping)
        task_q = self.request.GET.get('task_q')
        if task_q:
            queryset = queryset.filter(
                Q(title__icontains=task_q) | Q(description__icontains=task_q)
            )
        
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['status_filter'] = self.request.GET.get('status')
        context['priority_filter'] = self.request.GET.get('priority')
        context['assigned_to_filter'] = self.request.GET.get('assigned_to')
        context['task_q'] = self.request.GET.get('task_q') or ''
        context['user_q'] = self.request.GET.get('user_q') or ''
        context['status_choices'] = Task.STATUS_CHOICES
        context['priority_choices'] = Task.PRIORITY_CHOICES
        context['now'] = timezone.now()

        # Get unread notification count
        context['unread_notifications'] = TaskNotification.objects.filter(
            recipient=user,
            is_read=False
        ).count()

        if getattr(user, 'is_site_admin', False) or user.is_staff:
            context['assignees'] = User.objects.filter(is_active=True, role='YETAKCHI').order_by('full_name')

        # Group tasks by batch_id + signature so one task row expands to assignees
        tasks = list(self.get_queryset())

        # If user search is provided, keep only batches containing that user
        user_q = (self.request.GET.get('user_q') or '').strip()
        if user_q:
            matched = [t for t in tasks if user_q.lower() in (t.assigned_to.full_name or '').lower()]
            matched_keys = {str(getattr(t, "batch_id", None) or t.id) for t in matched}
            tasks = [t for t in tasks if str(getattr(t, "batch_id", None) or t.id) in matched_keys]

        groups = {}
        for task in tasks:
            key = str(task.task_group_id or task.id)
            group = groups.get(key)
            if not group:
                group = {
                    "id": key,
                    "dom_id": f"task-group-{key}",
                    "tasks": [],
                    "latest_created_at": task.created_at,
                    "representative": task,
                    "task_group": task.task_group,
                }
                groups[key] = group
            group["tasks"].append(task)
            if task.created_at and task.created_at > group["latest_created_at"]:
                group["latest_created_at"] = task.created_at

        group_list = sorted(groups.values(), key=lambda g: g["latest_created_at"], reverse=True)

        def _status_for(tasks_list):
            statuses = {t.status for t in tasks_list}
            if len(statuses) == 1:
                return statuses.pop()
            return "ARALASH"

        def _priority_for(tasks_list):
            priorities = {t.priority for t in tasks_list}
            if len(priorities) == 1:
                return priorities.pop()
            return "ARALASH"

        for group in group_list:
            group["assignees_count"] = len(group["tasks"])
            group["status"] = _status_for(group["tasks"])
            group["priority"] = _priority_for(group["tasks"])
            # Sort inside group by assignee name for easier lookup
            group["tasks"].sort(key=lambda t: (t.assigned_to.full_name or "").lower())
            completed_count = sum(1 for t in group["tasks"] if t.status == 'YAKUNLANGAN')
            group["completed_count"] = completed_count
            if group["assignees_count"]:
                group["completed_percent"] = round((completed_count / group["assignees_count"]) * 100)
            else:
                group["completed_percent"] = 0

        paginator = Paginator(group_list, self.page_size)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['task_groups'] = page_obj.object_list
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        context['is_paginated'] = page_obj.has_other_pages()

        return context


class TaskCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Task
    form_class = TaskForm
    template_name = 'ishsiz_yoshlar/task_form.html'
    success_url = reverse_lazy('ishsiz_yoshlar:task_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        eligible_users = User.objects.filter(is_active=True, role='YETAKCHI')
        if not getattr(user, 'is_site_admin', False) and user.mahalla:
            eligible_users = eligible_users.filter(mahalla=user.mahalla)
        eligible_users = eligible_users.exclude(id=user.id)

        recipient_ids = {u.id for u in (form.cleaned_data.get('recipients') or [])}

        if form.cleaned_data.get('send_all_coordinators'):
            recipient_ids.update(eligible_users.filter(is_sector_coordinator=True).values_list('id', flat=True))
        if form.cleaned_data.get('send_all_leaders'):
            recipient_ids.update(eligible_users.values_list('id', flat=True))
        if form.cleaned_data.get('send_sector_1_coordinator'):
            recipient_ids.update(eligible_users.filter(sector=1, is_sector_coordinator=True).values_list('id', flat=True))
        if form.cleaned_data.get('send_sector_1_leaders'):
            recipient_ids.update(eligible_users.filter(sector=1, is_sector_coordinator=False).values_list('id', flat=True))
        if form.cleaned_data.get('send_sector_2_coordinator'):
            recipient_ids.update(eligible_users.filter(sector=2, is_sector_coordinator=True).values_list('id', flat=True))
        if form.cleaned_data.get('send_sector_2_leaders'):
            recipient_ids.update(eligible_users.filter(sector=2, is_sector_coordinator=False).values_list('id', flat=True))
        if form.cleaned_data.get('send_sector_3_coordinator'):
            recipient_ids.update(eligible_users.filter(sector=3, is_sector_coordinator=True).values_list('id', flat=True))
        if form.cleaned_data.get('send_sector_3_leaders'):
            recipient_ids.update(eligible_users.filter(sector=3, is_sector_coordinator=False).values_list('id', flat=True))
        if form.cleaned_data.get('send_sector_4_coordinator'):
            recipient_ids.update(eligible_users.filter(sector=4, is_sector_coordinator=True).values_list('id', flat=True))
        if form.cleaned_data.get('send_sector_4_leaders'):
            recipient_ids.update(eligible_users.filter(sector=4, is_sector_coordinator=False).values_list('id', flat=True))

        if not recipient_ids:
            messages.error(self.request, "Kamida bitta mas'ulni tanlang.")
            return self.form_invalid(form)

        recipients = eligible_users.filter(id__in=recipient_ids)

        # Create task group (umumiy topshiriq)
        task_group = TaskGroup.objects.create(
            title=form.cleaned_data.get('title'),
            description=form.cleaned_data.get('description'),
            priority=form.cleaned_data.get('priority'),
            created_by=self.request.user,
            target_youth=None,
            target_mahalla=None,
            due_date=form.cleaned_data.get('due_date'),
            attachment=form.cleaned_data.get('attachment'),
        )

        created_count = 0
        batch_id = uuid.uuid4()
        for recipient in recipients:
            task = Task.objects.create(
                title=task_group.title,
                description=task_group.description,
                priority=task_group.priority,
                assigned_to=recipient,
                created_by=self.request.user,
                target_youth=task_group.target_youth,
                target_mahalla=task_group.target_mahalla,
                due_date=task_group.due_date,
                attachment=task_group.attachment,
                batch_id=batch_id,
                task_group=task_group,
            )
            create_task_notification(task, 'TASK_CREATED', recipient)
            created_count += 1

        messages.success(self.request, f"Topshiriq {created_count} ta ijrochiga yuborildi.")
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        eligible_users = User.objects.filter(is_active=True, role='YETAKCHI')
        if not getattr(user, 'is_site_admin', False) and user.mahalla:
            eligible_users = eligible_users.filter(mahalla=user.mahalla)
        eligible_users = eligible_users.exclude(id=user.id)

        selected_ids = set()
        form = context.get('form')
        if form:
            selected_ids = {str(v) for v in (form['recipients'].value() or [])}

        context['recipient_options'] = [
            {
                'id': u.id,
                'name': u.full_name,
                'sector': u.sector or 0,
                'is_coordinator': u.is_sector_coordinator,
            }
            for u in eligible_users
        ]
        context['selected_recipient_ids'] = selected_ids
        return context


class TaskDetailView(LoginRequiredMixin, DetailView):
    model = Task
    template_name = 'ishsiz_yoshlar/task_detail.html'
    context_object_name = 'task'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Check if user has access to this task
        if not getattr(self.request.user, 'is_site_admin', False) and self.request.user != obj.assigned_to and self.request.user != obj.created_by:
            raise Http404("Sizda bu topshiriqni ko'rish huquqi yo'q.")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['responses'] = self.object.responses.select_related('user').all()
        context['notifications'] = TaskNotification.objects.filter(
            task=self.object,
            recipient=self.request.user
        ).order_by('-created_at')[:10]
        return context


class TaskUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Task
    form_class = TaskForm
    template_name = 'ishsiz_yoshlar/task_form.html'
    success_url = reverse_lazy('ishsiz_yoshlar:task_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        task = form.instance

        # Update group data and sync to other assignments in the same group
        group = task.task_group
        if group:
            group.title = task.title
            group.description = task.description
            group.priority = task.priority
            group.due_date = task.due_date
            group.target_youth = task.target_youth
            group.target_mahalla = task.target_mahalla
            group.attachment = task.attachment
            group.save()

            # Sync shared fields to all assignments
            Task.objects.filter(task_group=group).exclude(id=task.id).update(
                title=group.title,
                description=group.description,
                priority=group.priority,
                due_date=group.due_date,
                target_youth=group.target_youth,
                target_mahalla=group.target_mahalla,
                attachment=group.attachment,
            )
        
        # Notify assigned user about update (after saving)
        create_task_notification(form.instance, 'TASK_UPDATED', form.instance.assigned_to)
        
        messages.success(self.request, "Topshiriq muvaffaqiyatli yangilandi.")
        return response


class TaskDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Task
    template_name = 'ishsiz_yoshlar/confirm_delete.html'
    success_url = reverse_lazy('ishsiz_yoshlar:task_list')

    def delete(self, request, *args, **kwargs):
        task = self.get_object()
        group = task.task_group
        if group:
            # Delete entire group with all assignments
            group.delete()
            messages.success(request, "Topshiriq guruhi muvaffaqiyatli o'chirildi.")
            return redirect(self.success_url)
        messages.success(request, "Topshiriq muvaffaqiyatli o'chirildi.")
        return super().delete(request, *args, **kwargs)


class TaskResponseCreateView(LoginRequiredMixin, CreateView):
    model = TaskResponse
    form_class = TaskResponseForm
    template_name = 'ishsiz_yoshlar/task_response_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.task = get_object_or_404(Task, pk=kwargs['pk'])
        # Check if user is assigned to this task
        if request.user != self.task.assigned_to and not getattr(request.user, 'is_site_admin', False):
            messages.error(request, "Sizda bu topshiriqqa javob berish huquqi yo'q.")
            return redirect('ishsiz_yoshlar:task_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['task'] = self.task
        return context

    def form_valid(self, form):
        # Use update_or_create to handle both new and existing responses
        response_obj, created = TaskResponse.objects.update_or_create(
            task=self.task,
            user=self.request.user,
            defaults={
                'response_type': form.cleaned_data.get('response_type'),
                'comment': form.cleaned_data.get('comment'),
                'completion_file': form.cleaned_data.get('completion_file'),
            }
        )
        
        if created:
            messages.success(self.request, "Javob muvaffaqiyatli yuborildi.")
        else:
            messages.success(self.request, "Javob muvaffaqiyatli yangilandi.")
        
        # Notify task creator
        create_task_notification(self.task, 'TASK_RESPONSE', self.task.created_by)
        
        # Update task status based on response
        if form.cleaned_data.get('response_type') == 'BAJARILDI':
            self.task.status = 'TASDIQLANGAN'
            self.task.completed_at = None
            self.task.save()
            create_task_notification(self.task, 'TASK_COMPLETED', self.task.created_by)
        elif form.cleaned_data.get('response_type') == 'RAD_ETDIM':
            self.task.status = 'RAD_ETILGAN'
            self.task.save()
        elif form.cleaned_data.get('response_type') == 'MUAMMO_BOR':
            self.task.status = 'BAJARILMOQDA'
            self.task.save()
        
        return redirect('ishsiz_yoshlar:task_detail', pk=self.task.pk)

    def get_success_url(self):
        return reverse_lazy('ishsiz_yoshlar:task_detail', kwargs={'pk': self.task.pk})


class NotificationListView(LoginRequiredMixin, ListView):
    model = TaskNotification
    template_name = 'ishsiz_yoshlar/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        return TaskNotification.objects.filter(
            recipient=self.request.user
        ).select_related('task', 'recipient').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Mark all as read
        TaskNotification.objects.filter(
            recipient=self.request.user,
            is_read=False
        ).update(is_read=True)
        return context


class MarkNotificationReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(TaskNotification, pk=pk, recipient=request.user)
        notification.is_read = True
        notification.save()
        return HttpResponse(status=200)


class TaskAcceptView(LoginRequiredMixin, View):
    """View for accepting/confirming a task"""
    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        
        if request.user != task.assigned_to:
            messages.error(request, "Sizda bu topshiriqni tasdiqlash huquqi yo'q.")
            return redirect('ishsiz_yoshlar:task_list')
        
        # Create or update response
        response, created = TaskResponse.objects.update_or_create(
            task=task,
            user=request.user,
            defaults={
                'response_type': 'QABUL_QILDIM',
                'comment': request.POST.get('comment', '')
            }
        )
        
        task.status = 'BAJARILMOQDA'
        task.save()
        
        messages.success(request, "Topshiriq qabul qilindi!")
        create_task_notification(task, 'TASK_RESPONSE', task.created_by)
        
        return redirect('ishsiz_yoshlar:task_detail', pk=pk)


class TaskReviewView(LoginRequiredMixin, AdminRequiredMixin, View):
    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        action = request.POST.get('action')
        comment = request.POST.get('comment', '').strip()

        if action == 'approve':
            task.status = 'YAKUNLANGAN'
            task.completed_at = task.completed_at or timezone.now()
            task.save()
            create_task_notification(task, 'TASK_APPROVED', task.assigned_to)
            if comment:
                TaskResponse.objects.update_or_create(
                    task=task,
                    user=request.user,
                    defaults={'response_type': 'QABUL_QILDIM', 'comment': comment}
                )
            messages.success(request, "Topshiriq tasdiqlandi.")
        elif action == 'return':
            task.status = 'BAJARILMOQDA'
            task.completed_at = None
            task.save()
            create_task_notification(task, 'TASK_RETURNED', task.assigned_to)
            if comment:
                TaskResponse.objects.update_or_create(
                    task=task,
                    user=request.user,
                    defaults={'response_type': 'MUAMMO_BOR', 'comment': comment}
                )
            messages.warning(request, "Topshiriq qaytarildi.")
        elif action == 'reject':
            task.status = 'RAD_ETILGAN'
            task.completed_at = None
            task.save()
            create_task_notification(task, 'TASK_RETURNED', task.assigned_to)
            if comment:
                TaskResponse.objects.update_or_create(
                    task=task,
                    user=request.user,
                    defaults={'response_type': 'RAD_ETDIM', 'comment': comment}
                )
            messages.error(request, "Topshiriq rad etildi.")

        return redirect('ishsiz_yoshlar:task_detail', pk=pk)
