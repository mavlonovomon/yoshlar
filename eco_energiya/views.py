from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from .models import SolarPanel


class EcoEnergiyaListView(LoginRequiredMixin, TemplateView):
    template_name = "eco_energiya/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["panels"] = SolarPanel.objects.select_related("mahalla").all()
        context["is_editor"] = getattr(self.request.user, "is_site_admin", False)
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

    panel.is_installed = is_installed
    panel.capacity_kw = capacity_kw if capacity_kw else None
    panel.installed_date = installed_date if installed_date else None
    panel.updated_by = request.user
    panel.save()

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
