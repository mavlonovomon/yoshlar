from django.contrib import admin
from .models import (
    FiveInitiativeApplicationEntry,
    FiveInitiativeApplicationSnapshot,
    FiveInitiativeEvent,
    FiveInitiativePhoto,
    FiveInitiativeSvodNorm,
)


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


@admin.register(FiveInitiativeApplicationSnapshot)
class FiveInitiativeApplicationSnapshotAdmin(admin.ModelAdmin):
    list_display = ('id', 'year', 'source_file_name', 'created_at', 'uploaded_by')
    list_filter = ('year', 'created_at')
    search_fields = ('source_file_name', 'uploaded_by__username', 'uploaded_by__full_name')


@admin.register(FiveInitiativeApplicationEntry)
class FiveInitiativeApplicationEntryAdmin(admin.ModelAdmin):
    list_display = ('snapshot', 'mahalla', 'participant_name', 'pinfl', 'selection_category', 'direction')
    list_filter = ('snapshot', 'selection_category', 'direction', 'mahalla')
    search_fields = ('participant_name', 'pinfl', 'mahalla_name_raw')


@admin.register(FiveInitiativeSvodNorm)
class FiveInitiativeSvodNormAdmin(admin.ModelAdmin):
    list_display = ('row_order', 'selection_category', 'direction', 'age_category', 'gender', 'norma')
    list_filter = ('selection_category', 'gender')
    search_fields = ('selection_category', 'direction', 'age_category')
    ordering = ('row_order',)
