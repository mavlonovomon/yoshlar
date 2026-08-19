from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from .models import SolarPanel


class EcoEnergiyaListView(LoginRequiredMixin, TemplateView):
    template_name = "eco_energiya/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        panels = SolarPanel.objects.select_related("mahalla").prefetch_related("mahalla__leaders").all()
        context["panels"] = panels
        context["is_editor"] = getattr(self.request.user, "is_site_admin", False)
        context["total_count"] = panels.count()
        context["installed_count"] = panels.filter(is_installed=True).count()
        context["not_installed_count"] = panels.filter(is_installed=False).count()
        context["total_capacity"] = panels.filter(is_installed=True).aggregate(
            total=Sum("capacity_kw")
        )["total"] or 0
        return context


@login_required
def solar_panel_update(request, pk):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST method required"}, status=405)

    if not getattr(request.user, "is_site_admin", False):
        return JsonResponse({"success": False, "error": "Ruxsat yo'q"}, status=403)

    panel = get_object_or_404(SolarPanel, pk=pk)

    is_installed = request.POST.get("is_installed") == "on"
    capacity_kw = request.POST.get("capacity_kw", "").strip()
    installed_date = request.POST.get("installed_date", "").strip()

    if capacity_kw:
        try:
            capacity_kw = Decimal(capacity_kw)
        except (InvalidOperation, ValueError):
            return JsonResponse({"success": False, "error": "Noto'g'ri quvvat qiymati"}, status=400)
    else:
        capacity_kw = None

    if installed_date:
        try:
            installed_date = datetime.strptime(installed_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return JsonResponse({"success": False, "error": "Noto'g'ri sana formati"}, status=400)
    else:
        installed_date = None

    panel.is_installed = is_installed
    panel.capacity_kw = capacity_kw
    panel.installed_date = installed_date
    panel.updated_by = request.user

    try:
        panel.save()
    except Exception as e:
        return JsonResponse({"success": False, "error": "Saqlashda xatolik yuz berdi"}, status=500)

    return JsonResponse({
        "success": True,
        "panel": {
            "id": panel.id,
            "mahalla_name": panel.mahalla.name,
            "is_installed": panel.is_installed,
            "capacity_kw": str(panel.capacity_kw) if panel.capacity_kw else None,
            "installed_date": panel.installed_date.isoformat() if panel.installed_date else None,
        }
    })
