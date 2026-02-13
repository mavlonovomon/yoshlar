from django.contrib import admin
from .models import AttendanceSession, AttendanceRecord


class AttendanceRecordInline(admin.TabularInline):
    model = AttendanceRecord
    extra = 0


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ('session_type', 'session_date', 'created_by')
    list_filter = ('session_type', 'session_date')
    search_fields = ('reason',)
    inlines = [AttendanceRecordInline]


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('session', 'leader', 'status', 'updated_at')
    list_filter = ('status',)
    search_fields = ('leader__full_name',)
