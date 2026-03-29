from django.contrib import admin

from .models import EkinYerEntry, EkinYerSnapshot


@admin.register(EkinYerSnapshot)
class EkinYerSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "source_file_name", "created_at", "uploaded_by")
    search_fields = ("source_file_name", "uploaded_by__full_name", "uploaded_by__username")


@admin.register(EkinYerEntry)
class EkinYerEntryAdmin(admin.ModelAdmin):
    list_display = (
        "winner_name",
        "winner_birth_date",
        "land_neighborhood_name",
        "match_status",
        "linked_yosh",
        "snapshot",
    )
    list_filter = ("match_status", "is_youth_age", "land_neighborhood_name", "snapshot")
    search_fields = ("winner_name", "winner_name_normalized", "linked_yosh__fullname", "winner_phone")
    autocomplete_fields = ("linked_yosh",)

