from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView
import json

from core.models import Mahalla
from .forms import FiveInitiativeEventForm
from .models import FiveInitiativeEvent, FiveInitiativePhoto


class LeaderRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return getattr(user, "is_site_admin", False) or getattr(user, "role", None) == "YETAKCHI"


class MahallaRestrictedMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not getattr(user, "is_site_admin", False) and user.mahalla:
            if hasattr(self.model, "mahalla"):
                return queryset.filter(mahalla=user.mahalla)
        return queryset


class FiveInitiativeListView(LoginRequiredMixin, ListView):
    model = FiveInitiativeEvent
    template_name = "beshtashabbus/list.html"
    context_object_name = "events"
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        queryset = FiveInitiativeEvent.objects.select_related("mahalla").annotate(
            photo_count=Count("photos", distinct=True)
        )

        if not getattr(user, "is_site_admin", False) and user.mahalla:
            queryset = queryset.filter(mahalla=user.mahalla)

        search = self.request.GET.get("q")
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))

        mahalla_id = self.request.GET.get("mahalla")
        if mahalla_id:
            queryset = queryset.filter(mahalla_id=mahalla_id)

        direction = self.request.GET.get("direction")
        if direction:
            queryset = queryset.filter(direction=direction)

        return queryset.order_by("-event_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        try:
            mahalla_id = self.request.GET.get("mahalla")
            context["selected_mahalla"] = int(mahalla_id) if mahalla_id else None
        except (ValueError, TypeError):
            context["selected_mahalla"] = None

        if getattr(user, "is_site_admin", False):
            context["mahallas"] = Mahalla.objects.all()
        else:
            context["mahallas"] = (
                Mahalla.objects.filter(id=user.mahalla.id) if user.mahalla else Mahalla.objects.none()
            )

        context["directions"] = FiveInitiativeEvent.DIRECTION_CHOICES
        context["selected_direction"] = self.request.GET.get("direction")
        return context


class FiveInitiativeCreateView(LoginRequiredMixin, LeaderRequiredMixin, CreateView):
    model = FiveInitiativeEvent
    form_class = FiveInitiativeEventForm
    template_name = "beshtashabbus/form.html"
    success_url = reverse_lazy("beshtashabbus:list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        self._save_photos(form)
        messages.success(self.request, "Tadbir muvaffaqiyatli qo'shildi.")
        return response

    def _save_photos(self, form):
        for image in form.get_new_photos():
            FiveInitiativePhoto.objects.create(event=self.object, image=image)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title_options_json"] = json.dumps(self.form_class.get_title_options())
        return context


class FiveInitiativeUpdateView(LoginRequiredMixin, LeaderRequiredMixin, MahallaRestrictedMixin, UpdateView):
    model = FiveInitiativeEvent
    form_class = FiveInitiativeEventForm
    template_name = "beshtashabbus/form.html"
    success_url = reverse_lazy("beshtashabbus:list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        self._save_photos(form)
        messages.success(self.request, "Tadbir yangilandi.")
        return response

    def _save_photos(self, form):
        for image in form.get_new_photos():
            FiveInitiativePhoto.objects.create(event=self.object, image=image)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title_options_json"] = json.dumps(self.form_class.get_title_options())
        return context


class FiveInitiativeDetailView(LoginRequiredMixin, MahallaRestrictedMixin, DetailView):
    model = FiveInitiativeEvent
    template_name = "beshtashabbus/detail.html"
    context_object_name = "event"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["photos"] = self.object.photos.all()
        return context


from .views_applications import (
    FiveInitiativeApplicationExtendedSvodView,
    FiveInitiativeApplicationSubmitView,
    FiveInitiativeApplicationSvodTabsView,
    FiveInitiativeApplicationSvodView,
    FiveInitiativeApplicationUploadView,
    FiveInitiativeSportTypesView,
    FiveInitiativeSvodNormaView,
    FiveInitiativeYouthListView,
)
