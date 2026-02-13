from django.contrib import admin
from .models import FiveInitiativeEvent, FiveInitiativePhoto


class FiveInitiativePhotoInline(admin.TabularInline):
    model = FiveInitiativePhoto
    extra = 0


@admin.register(FiveInitiativeEvent)
class FiveInitiativeEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'direction', 'mahalla', 'event_date', 'coverage')
    list_filter = ('direction', 'mahalla')
    search_fields = ('title', 'description')
    inlines = [FiveInitiativePhotoInline]


@admin.register(FiveInitiativePhoto)
class FiveInitiativePhotoAdmin(admin.ModelAdmin):
    list_display = ('event', 'created_at')
    list_filter = ('created_at',)
