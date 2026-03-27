from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.db.models import Count, Q
from django.contrib import messages

from core.models import Mahalla
from .models import MigrationYouth, MigrationMeeting
from .forms import MigrationYouthForm, MigrationMeetingForm, PROVINCE_MAP


class LeaderRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return getattr(user, 'role', None) == 'YETAKCHI' or getattr(user, 'is_site_admin', False)


class MahallaRestrictedMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not getattr(user, 'is_site_admin', False) and user.mahalla:
            if hasattr(self.model, 'yosh'):
                return queryset.filter(yosh__mahalla=user.mahalla)
            if hasattr(self.model, 'mahalla'):
                return queryset.filter(mahalla=user.mahalla)
            if self.model == Mahalla:
                return queryset.filter(id=user.mahalla.id)
        return queryset


class MigrationYouthListView(LoginRequiredMixin, ListView):
    model = MigrationYouth
    template_name = 'migratsiya/list.html'
    context_object_name = 'youths'
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        queryset = MigrationYouth.objects.select_related('yosh', 'yosh__mahalla').prefetch_related('yosh__mahalla__leaders').annotate(
            meeting_count=Count('meetings', distinct=True)
        )

        if not getattr(user, 'is_site_admin', False) and user.mahalla:
            queryset = queryset.filter(yosh__mahalla=user.mahalla)

        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(yosh__fullname__icontains=search) |
                Q(yosh__passport_number__icontains=search) |
                Q(yosh__jshshir__icontains=search) |
                Q(yosh__phone_number__icontains=search)
            )

        mahalla_id = self.request.GET.get('mahalla')
        if mahalla_id:
            queryset = queryset.filter(yosh__mahalla_id=mahalla_id)

        reason = self.request.GET.get('reason')
        if reason:
            queryset = queryset.filter(reason=reason)

        return queryset.order_by('yosh__fullname')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        try:
            mahalla_id = self.request.GET.get('mahalla')
            context['selected_mahalla'] = int(mahalla_id) if mahalla_id else None
        except (ValueError, TypeError):
            context['selected_mahalla'] = None

        context['selected_reason'] = self.request.GET.get('reason')

        if getattr(user, 'is_site_admin', False):
            context['mahallas'] = Mahalla.objects.all()
        else:
            context['mahallas'] = Mahalla.objects.filter(id=user.mahalla.id) if user.mahalla else Mahalla.objects.none()

        context['reasons'] = MigrationYouth.REASON_CHOICES
        return context


class MigrationYouthCreateView(LoginRequiredMixin, LeaderRequiredMixin, CreateView):
    model = MigrationYouth
    form_class = MigrationYouthForm
    template_name = 'migratsiya/form.html'
    success_url = reverse_lazy('migratsiya:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['province_map'] = PROVINCE_MAP
        return context

    def form_valid(self, form):
        user = self.request.user
        yosh = form.cleaned_data.get('yosh')
        if not getattr(user, 'is_site_admin', False) and user.mahalla and yosh.mahalla != user.mahalla:
            messages.error(self.request, "Siz faqat o'zingizning mahallangizdagi yoshlarni qo'shishingiz mumkin.")
            return self.form_invalid(form)
        messages.success(self.request, "Migratsiyadagi yosh muvaffaqiyatli qo'shildi.")
        return super().form_valid(form)


class MigrationYouthUpdateView(LoginRequiredMixin, LeaderRequiredMixin, MahallaRestrictedMixin, UpdateView):
    model = MigrationYouth
    form_class = MigrationYouthForm
    template_name = 'migratsiya/form.html'
    success_url = reverse_lazy('migratsiya:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['province_map'] = PROVINCE_MAP
        return context


class MigrationYouthDetailView(LoginRequiredMixin, MahallaRestrictedMixin, DetailView):
    model = MigrationYouth
    template_name = 'migratsiya/detail.html'
    context_object_name = 'youth'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['meetings'] = self.object.meetings.all().order_by('-meeting_date')
        return context


class MeetingCreateView(LoginRequiredMixin, MahallaRestrictedMixin, CreateView):
    model = MigrationMeeting
    form_class = MigrationMeetingForm
    template_name = 'migratsiya/meeting_form.html'

    def dispatch(self, request, *args, **kwargs):
        youth = get_object_or_404(MigrationYouth, pk=self.kwargs['pk'])
        user = request.user
        if not getattr(user, 'is_site_admin', False) and user.mahalla and youth.yosh.mahalla != user.mahalla:
            messages.error(request, "Sizda bu yoshga kirish huquqi yo'q.")
            return redirect('migratsiya:list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['youth'] = get_object_or_404(MigrationYouth, pk=self.kwargs['pk'])
        return context

    def form_valid(self, form):
        youth = get_object_or_404(MigrationYouth, pk=self.kwargs['pk'])
        form.instance.migration_youth = youth
        messages.success(self.request, "Suhbat muvaffaqiyatli qo'shildi.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('migratsiya:detail', kwargs={'pk': self.kwargs['pk']})
