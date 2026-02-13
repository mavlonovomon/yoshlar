from django.contrib import admin
from .models import OtaliqLeader, OtaliqYouth, OtaliqMeeting, OtaliqAssistance

@admin.register(OtaliqLeader)
class OtaliqLeaderAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'organization_name', 'position', 'level', 'phone_number')
    list_filter = ('organization_type', 'level')
    search_fields = ('full_name', 'organization_name')

class OtaliqMeetingInline(admin.TabularInline):
    model = OtaliqMeeting
    extra = 1

class OtaliqAssistanceInline(admin.StackedInline):
    model = OtaliqAssistance
    can_delete = False

@admin.register(OtaliqYouth)
class OtaliqYouthAdmin(admin.ModelAdmin):
    list_display = ('get_fullname', 'category', 'leader', 'get_mahalla', 'created_at')
    list_filter = ('category', 'yosh__mahalla', 'leader')
    search_fields = ('yosh__fullname', 'yosh__passport_number')
    inlines = [OtaliqMeetingInline, OtaliqAssistanceInline]

    def get_fullname(self, obj):
        return obj.yosh.fullname
    get_fullname.short_description = "F.I.Sh"

    def get_mahalla(self, obj):
        return obj.yosh.mahalla.name
    get_mahalla.short_description = "Mahalla"

@admin.register(OtaliqMeeting)
class OtaliqMeetingAdmin(admin.ModelAdmin):
    list_display = ('otaliq_youth', 'meeting_date', 'created_at')
    list_filter = ('meeting_date',)

@admin.register(OtaliqAssistance)
class OtaliqAssistanceAdmin(admin.ModelAdmin):
    list_display = ('otaliq_youth', 'provided', 'assistance_type', 'date_provided')
    list_filter = ('provided', 'assistance_type')
