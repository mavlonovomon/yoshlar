from django.contrib import admin
from .models import MigrationYouth, MigrationMeeting


class MigrationMeetingInline(admin.TabularInline):
    model = MigrationMeeting
    extra = 0


@admin.register(MigrationYouth)
class MigrationYouthAdmin(admin.ModelAdmin):
    list_display = ('get_fullname', 'reason', 'departure_date', 'destination_country', 'get_mahalla')
    list_filter = ('reason', 'destination_country', 'yosh__mahalla')
    search_fields = ('yosh__fullname', 'yosh__passport_number', 'yosh__jshshir')
    autocomplete_fields = ['yosh']
    inlines = [MigrationMeetingInline]

    def get_fullname(self, obj):
        return obj.yosh.fullname
    get_fullname.short_description = 'F.I.Sh'

    def get_mahalla(self, obj):
        return obj.yosh.mahalla.name
    get_mahalla.short_description = 'Mahalla'


@admin.register(MigrationMeeting)
class MigrationMeetingAdmin(admin.ModelAdmin):
    list_display = ('migration_youth', 'meeting_date', 'return_date')
    list_filter = ('meeting_date',)
    search_fields = ('migration_youth__yosh__fullname',)
