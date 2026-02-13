from django.contrib import admin
from .models import DisciplineAction


@admin.register(DisciplineAction)
class DisciplineActionAdmin(admin.ModelAdmin):
    list_display = ('action_date', 'employee', 'action_type', 'status', 'end_date', 'resolved_date', 'created_by')
    list_filter = ('action_type', 'status', 'action_date')
    search_fields = ('employee__full_name', 'employee__username', 'employee__pinfl', 'reason')
