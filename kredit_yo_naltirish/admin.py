from django.contrib import admin
from .models import CreditCandidate, CreditMonitoringEntry, CreditMonitoringFile


@admin.register(CreditCandidate)
class CreditCandidateAdmin(admin.ModelAdmin):
    list_display = ("yosh", "stage", "monitoring_enabled", "created_at")
    list_filter = ("stage", "monitoring_enabled")
    search_fields = ("yosh__fullname", "yosh__jshshir", "yosh__passport_number")


@admin.register(CreditMonitoringEntry)
class CreditMonitoringEntryAdmin(admin.ModelAdmin):
    list_display = ("candidate", "monitoring_date", "created_by", "created_at")
    list_filter = ("monitoring_date",)
    search_fields = ("candidate__yosh__fullname",)


@admin.register(CreditMonitoringFile)
class CreditMonitoringFileAdmin(admin.ModelAdmin):
    list_display = ("monitoring_entry", "file_type", "uploaded_at")
    list_filter = ("file_type",)
