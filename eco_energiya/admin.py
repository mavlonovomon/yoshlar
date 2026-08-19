from django.contrib import admin
from .models import SolarPanel


@admin.register(SolarPanel)
class SolarPanelAdmin(admin.ModelAdmin):
    list_display = ("mahalla", "is_installed", "capacity_kw", "installed_date", "updated_at")
    list_filter = ("is_installed",)
    search_fields = ("mahalla__name",)
