from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.http import HttpResponse
from django.db.models import Count, Q
from django.contrib import messages

from core.models import Mahalla
from core.view_helpers import apply_sorting, normalize_sort_params
from .models import RaidEvent, RaidPhoto
from .forms import RaidEventForm


class LeaderRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return getattr(user, 'is_site_admin', False) or getattr(user, 'role', None) == 'YETAKCHI'


class MahallaRestrictedMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not getattr(user, 'is_site_admin', False) and user.mahalla:
            if hasattr(self.model, 'mahalla'):
                return queryset.filter(mahalla=user.mahalla)
        return queryset


class RaidEventListView(LoginRequiredMixin, ListView):
    model = RaidEvent
    template_name = 'reyd/list.html'
    context_object_name = 'events'
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        queryset = RaidEvent.objects.select_related('mahalla').annotate(
            photo_count=Count('photos', distinct=True)
        )

        if not getattr(user, 'is_site_admin', False) and user.mahalla:
            queryset = queryset.filter(mahalla=user.mahalla)

        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))

        mahalla_id = self.request.GET.get('mahalla')
        if mahalla_id:
            queryset = queryset.filter(mahalla_id=mahalla_id)

        event_type = self.request.GET.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        sort_field, sort_direction = normalize_sort_params(
            self.request,
            {'title', 'mahalla', 'event_date', 'event_type', 'photo_count'},
            'event_date',
            'desc',
        )
        self.sort_field = sort_field
        self.sort_direction = sort_direction
        sort_map = {
            'title': 'title',
            'mahalla': 'mahalla__name',
            'event_date': 'event_date',
            'event_type': 'event_type',
            'photo_count': 'photo_count',
        }
        return apply_sorting(queryset, sort_field, sort_direction, sort_map, 'event_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        try:
            mahalla_id = self.request.GET.get('mahalla')
            context['selected_mahalla'] = int(mahalla_id) if mahalla_id else None
        except (ValueError, TypeError):
            context['selected_mahalla'] = None
        if getattr(user, 'is_site_admin', False):
            context['mahallas'] = Mahalla.objects.all()
        else:
            context['mahallas'] = Mahalla.objects.filter(id=user.mahalla.id) if user.mahalla else Mahalla.objects.none()
        context['types'] = RaidEvent.TYPE_CHOICES
        context['selected_type'] = self.request.GET.get('event_type')
        context['sort_field'] = getattr(self, 'sort_field', 'event_date')
        context['sort_direction'] = getattr(self, 'sort_direction', 'desc')
        return context


class RaidEventCreateView(LoginRequiredMixin, LeaderRequiredMixin, CreateView):
    model = RaidEvent
    form_class = RaidEventForm
    template_name = 'reyd/form.html'
    success_url = reverse_lazy('reyd:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        self._save_photos(form)
        messages.success(self.request, "Reyd tadbiri muvaffaqiyatli qo'shildi.")
        return response

    def _save_photos(self, form):
        for image in form.get_new_photos():
            RaidPhoto.objects.create(event=self.object, image=image)


class RaidEventUpdateView(LoginRequiredMixin, LeaderRequiredMixin, MahallaRestrictedMixin, UpdateView):
    model = RaidEvent
    form_class = RaidEventForm
    template_name = 'reyd/form.html'
    success_url = reverse_lazy('reyd:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        self._save_photos(form)
        messages.success(self.request, "Reyd tadbiri yangilandi.")
        return response

    def _save_photos(self, form):
        for image in form.get_new_photos():
            RaidPhoto.objects.create(event=self.object, image=image)


class RaidEventDetailView(LoginRequiredMixin, MahallaRestrictedMixin, DetailView):
    model = RaidEvent
    template_name = 'reyd/detail.html'
    context_object_name = 'event'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['photos'] = self.object.photos.all()
        return context


class RaidEventPDFView(LoginRequiredMixin, DetailView):
    model = RaidEvent

    def get(self, request, *args, **kwargs):
        event_obj = self.get_object()
        from .pdf_generator import generate_reyd_pdf
        pdf_buffer = generate_reyd_pdf(event_obj)

        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="profilaktika_{event_obj.pk}.pdf"'
        return response
