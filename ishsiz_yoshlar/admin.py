from django.contrib import admin
from .models import (
    ResponsibleLeader,
    UnemployedYouth,
    YouthMeeting,
    AssistanceInfo,
    TaskGroup,
    Task,
    TaskResponse,
    TaskNotification,
)

class MeetingInline(admin.TabularInline):
    model = YouthMeeting
    extra = 1

class AssistanceInline(admin.StackedInline):
    model = AssistanceInfo
    can_delete = False
    verbose_name_plural = 'Yordam ko‘rsatish holati'

@admin.register(ResponsibleLeader)
class ResponsibleLeaderAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'position', 'level', 'phone_number', 'organization')
    list_filter = ('level',)
    search_fields = ('full_name', 'position', 'organization')

@admin.register(UnemployedYouth)
class UnemployedYouthAdmin(admin.ModelAdmin):
    list_display = ('get_fullname', 'get_passport', 'category', 'leader', 'get_mahalla', 'created_at')
    list_filter = ('category', 'leader__level', 'yosh__mahalla')
    search_fields = ('yosh__fullname', 'yosh__passport_number', 'yosh__jshshir')
    autocomplete_fields = ['yosh', 'leader']
    inlines = [MeetingInline, AssistanceInline]

    def get_fullname(self, obj):
        return obj.yosh.fullname
    get_fullname.short_description = "F.I.Sh"

    def get_passport(self, obj):
        return obj.yosh.passport_number
    get_passport.short_description = "Pasport"

    def get_mahalla(self, obj):
        return obj.yosh.mahalla.name
    get_mahalla.short_description = "Mahalla"

@admin.register(YouthMeeting)
class YouthMeetingAdmin(admin.ModelAdmin):
    list_display = ('unemployed_youth', 'meeting_date', 'created_at')
    list_filter = ('meeting_date',)
    search_fields = ('unemployed_youth__yosh__fullname',)

@admin.register(AssistanceInfo)
class AssistanceInfoAdmin(admin.ModelAdmin):
    list_display = ('unemployed_youth', 'provided', 'assistance_type', 'date_provided')
    list_filter = ('provided', 'assistance_type')
    search_fields = ('unemployed_youth__yosh__fullname',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'assigned_to', 'status', 'priority', 'due_date', 'created_at')
    list_filter = ('status', 'priority', 'assigned_to')
    search_fields = ('title', 'assigned_to__full_name', 'created_by__full_name')
    autocomplete_fields = ('assigned_to', 'created_by', 'target_youth', 'target_mahalla')


@admin.register(TaskGroup)
class TaskGroupAdmin(admin.ModelAdmin):
    list_display = ('title', 'priority', 'due_date', 'created_by', 'created_at')
    list_filter = ('priority',)
    search_fields = ('title', 'created_by__full_name')
    autocomplete_fields = ('created_by', 'target_youth', 'target_mahalla')


@admin.register(TaskResponse)
class TaskResponseAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'response_type', 'responded_at')
    list_filter = ('response_type',)
    search_fields = ('task__title', 'user__full_name')
    autocomplete_fields = ('task', 'user')


@admin.register(TaskNotification)
class TaskNotificationAdmin(admin.ModelAdmin):
    list_display = ('notification_type', 'recipient', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')
    search_fields = ('recipient__full_name', 'message')
    autocomplete_fields = ('task', 'recipient')
