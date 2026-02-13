from django.shortcuts import redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.db.models import Q
from django.contrib import messages

from core.models import User
from .models import AttendanceSession, AttendanceRecord
from .forms import AttendanceSessionForm


class SuperAdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_superuser or getattr(user, 'role', None) in {'SUPER_ADMIN', 'RAHBAR'}


class AttendanceListView(LoginRequiredMixin, ListView):
    model = AttendanceSession
    template_name = 'yoqlama/list.html'
    context_object_name = 'sessions'
    paginate_by = 25

    def get_queryset(self):
        queryset = AttendanceSession.objects.select_related('created_by')
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(Q(reason__icontains=search))

        session_type = self.request.GET.get('session_type')
        if session_type:
            queryset = queryset.filter(session_type=session_type)

        return queryset.order_by('-session_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['types'] = AttendanceSession.SESSION_TYPE_CHOICES
        context['selected_type'] = self.request.GET.get('session_type')
        return context


class AttendanceCreateView(LoginRequiredMixin, SuperAdminRequiredMixin, CreateView):
    model = AttendanceSession
    form_class = AttendanceSessionForm
    template_name = 'yoqlama/form.html'
    success_url = reverse_lazy('yoqlama:list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)

        leaders = User.objects.filter(is_active=True, role='YETAKCHI').order_by('full_name')
        records = [
            AttendanceRecord(session=self.object, leader=leader)
            for leader in leaders
        ]
        AttendanceRecord.objects.bulk_create(records)

        messages.success(self.request, "Yo'qlama yaratildi. Endi yetakchilar holatini belgilang.")
        return response


class AttendanceUpdateView(LoginRequiredMixin, SuperAdminRequiredMixin, UpdateView):
    model = AttendanceSession
    form_class = AttendanceSessionForm
    template_name = 'yoqlama/form.html'
    success_url = reverse_lazy('yoqlama:list')

    def form_valid(self, form):
        messages.success(self.request, "Yo'qlama yangilandi.")
        return super().form_valid(form)


class AttendanceDetailView(LoginRequiredMixin, DetailView):
    model = AttendanceSession
    template_name = 'yoqlama/detail.html'
    context_object_name = 'session'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_status = self.request.GET.get('status')
        records_qs = self.object.records.select_related('leader').all()
        status_codes = {code for code, _ in AttendanceRecord.STATUS_CHOICES}

        if selected_status == 'NONE':
            records_qs = records_qs.filter(status__isnull=True)
        elif selected_status in status_codes:
            records_qs = records_qs.filter(status=selected_status)
        else:
            selected_status = ''

        context['records'] = records_qs
        context['status_choices'] = AttendanceRecord.STATUS_CHOICES
        context['selected_status'] = selected_status
        return context

    def post(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user, 'role', None) in {'SUPER_ADMIN', 'RAHBAR'}):
            messages.error(request, "Sizda yo'qlama qilish huquqi yo'q.")
            return redirect('yoqlama:detail', pk=kwargs.get('pk'))
        self.object = self.get_object()
        records = self.object.records.select_related('leader').all()

        for record in records:
            status_key = f'status_{record.id}'
            reason_key = f'reason_{record.id}'
            if status_key not in request.POST and reason_key not in request.POST:
                continue

            status_value = request.POST.get(status_key, '').strip()
            reason_value = request.POST.get(reason_key, '').strip()

            record.status = status_value or None
            record.reason = reason_value or None
            record.save(update_fields=['status', 'reason', 'updated_at'])

        messages.success(request, "Yo'qlama ma'lumotlari saqlandi.")
        filter_status = request.POST.get('filter_status')
        if filter_status:
            return redirect(f"{reverse_lazy('yoqlama:detail', kwargs={'pk': self.object.pk})}?status={filter_status}")
        return redirect('yoqlama:detail', pk=self.object.pk)
