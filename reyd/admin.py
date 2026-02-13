from django.contrib import admin
from .models import RaidEvent, RaidPhoto


class RaidPhotoInline(admin.TabularInline):
    model = RaidPhoto
    extra = 0


@admin.register(RaidEvent)
class RaidEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_type', 'mahalla', 'event_date', 'created_at')
    list_filter = ('event_type', 'mahalla')
    search_fields = ('title', 'description')
    inlines = [RaidPhotoInline]


@admin.register(RaidPhoto)
class RaidPhotoAdmin(admin.ModelAdmin):
    list_display = ('event', 'created_at')
    list_filter = ('created_at',)
