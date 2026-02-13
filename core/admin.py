from django.contrib import admin
from .models import (
    Mahalla,
    User,
    Yosh,
    Uchrashuv,
    LeaderKpiSnapshot,
    MutolaaStatSnapshot,
    MutolaaMahallaStat,
    MutolaaMahallaAlias,
    UstozAiStatSnapshot,
    UstozAiMahallaStat,
    UstozAiMahallaAlias,
    UzchessStatSnapshot,
    UzchessMahallaStat,
    UzchessMahallaAlias,
    QizlarAkademiyasiStatSnapshot,
    QizlarAkademiyasiMahallaStat,
    QizlarAkademiyasiMahallaAlias,
)
from django.contrib.auth.admin import UserAdmin


def _admin_has_permission(request):
    user = request.user
    return bool(
        user
        and user.is_active
        and (user.is_superuser or getattr(user, 'role', None) == 'SUPER_ADMIN')
    )


admin.site.has_permission = _admin_has_permission


class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': (
            'role', 'full_name', 'pinfl', 'phone_number', 'birth_date',
            'mahalla', 'sector', 'is_sector_coordinator', 'position',
            'address', 'education', 'specialization', 'work_start_date',
            'telegram_username', 'emergency_contact', 'about', 'profile_image'
        )}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': (
            'role', 'full_name', 'pinfl', 'phone_number', 'birth_date',
            'mahalla', 'sector', 'is_sector_coordinator', 'position',
            'address', 'education', 'specialization', 'work_start_date',
            'telegram_username', 'emergency_contact', 'about', 'profile_image'
        )}),
    )
    list_display = ('username', 'full_name', 'pinfl', 'phone_number', 'role', 'mahalla', 'sector', 'is_sector_coordinator', 'is_staff')
    list_filter = ('role', 'mahalla', 'sector', 'is_sector_coordinator')

admin.site.register(User, CustomUserAdmin)
@admin.register(Mahalla)
class MahallaAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Yosh)
class YoshAdmin(admin.ModelAdmin):
    search_fields = ('fullname', 'passport_number', 'jshshir')
    list_display = ('fullname', 'passport_number', 'mahalla')
    list_filter = ('mahalla',)

admin.site.register(Uchrashuv)


@admin.register(LeaderKpiSnapshot)
class LeaderKpiSnapshotAdmin(admin.ModelAdmin):
    list_display = ('user', 'date_from', 'date_to', 'total_score', 'created_at')
    list_filter = ('date_from', 'date_to')
    search_fields = ('user__full_name', 'user__username', 'user__mahalla__name')
    list_select_related = ('user',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(MutolaaMahallaAlias)
class MutolaaMahallaAliasAdmin(admin.ModelAdmin):
    list_display = ('api_name', 'mahalla', 'last_seen')
    list_display_links = ('api_name',)
    list_editable = ('mahalla',)
    list_filter = ('mahalla',)
    search_fields = ('api_name', 'api_norm', 'mahalla__name')
    list_select_related = ('mahalla',)
    ordering = ('api_name',)


@admin.register(MutolaaStatSnapshot)
class MutolaaStatSnapshotAdmin(admin.ModelAdmin):
    list_display = ('snapshot_date', 'fetched_at', 'source_url')
    readonly_fields = ('snapshot_date', 'fetched_at', 'source_url', 'raw_payload')


@admin.register(MutolaaMahallaStat)
class MutolaaMahallaStatAdmin(admin.ModelAdmin):
    list_display = ('snapshot', 'mahalla', 'mahalla_name')
    list_filter = ('snapshot', 'mahalla')
    search_fields = ('mahalla_name',)


@admin.register(UstozAiMahallaAlias)
class UstozAiMahallaAliasAdmin(admin.ModelAdmin):
    list_display = ('api_name', 'mahalla', 'last_seen')
    list_display_links = ('api_name',)
    list_editable = ('mahalla',)
    list_filter = ('mahalla',)
    search_fields = ('api_name', 'api_norm', 'mahalla__name')
    list_select_related = ('mahalla',)
    ordering = ('api_name',)


@admin.register(UstozAiStatSnapshot)
class UstozAiStatSnapshotAdmin(admin.ModelAdmin):
    list_display = ('snapshot_date', 'fetched_at', 'source_url')
    readonly_fields = ('snapshot_date', 'fetched_at', 'source_url', 'raw_payload')


@admin.register(UstozAiMahallaStat)
class UstozAiMahallaStatAdmin(admin.ModelAdmin):
    list_display = ('snapshot', 'mahalla', 'area_name')
    list_filter = ('snapshot', 'mahalla')
    search_fields = ('area_name',)


@admin.register(UzchessMahallaAlias)
class UzchessMahallaAliasAdmin(admin.ModelAdmin):
    list_display = ('api_name', 'mahalla', 'last_seen')
    list_display_links = ('api_name',)
    list_editable = ('mahalla',)
    list_filter = ('mahalla',)
    search_fields = ('api_name', 'api_norm', 'mahalla__name')
    list_select_related = ('mahalla',)
    ordering = ('api_name',)


@admin.register(UzchessStatSnapshot)
class UzchessStatSnapshotAdmin(admin.ModelAdmin):
    list_display = ('snapshot_date', 'fetched_at', 'source_url')
    readonly_fields = ('snapshot_date', 'fetched_at', 'source_url', 'raw_payload')


@admin.register(UzchessMahallaStat)
class UzchessMahallaStatAdmin(admin.ModelAdmin):
    list_display = ('snapshot', 'mahalla', 'area_name')
    list_filter = ('snapshot', 'mahalla')
    search_fields = ('area_name',)


@admin.register(QizlarAkademiyasiMahallaAlias)
class QizlarAkademiyasiMahallaAliasAdmin(admin.ModelAdmin):
    list_display = ('api_name', 'mahalla', 'last_seen')
    list_display_links = ('api_name',)
    list_editable = ('mahalla',)
    list_filter = ('mahalla',)
    search_fields = ('api_name', 'api_norm', 'mahalla__name')
    list_select_related = ('mahalla',)
    ordering = ('api_name',)


@admin.register(QizlarAkademiyasiStatSnapshot)
class QizlarAkademiyasiStatSnapshotAdmin(admin.ModelAdmin):
    list_display = ('snapshot_date', 'fetched_at', 'source_url')
    readonly_fields = ('snapshot_date', 'fetched_at', 'source_url', 'raw_payload')


@admin.register(QizlarAkademiyasiMahallaStat)
class QizlarAkademiyasiMahallaStatAdmin(admin.ModelAdmin):
    list_display = ('snapshot', 'mahalla', 'area_name')
    list_filter = ('snapshot', 'mahalla')
    search_fields = ('area_name',)


# Admin menyusida "Mega loyihalar" bo'limiga guruhlash
_original_get_app_list = admin.site.get_app_list


def _mega_get_app_list(request, app_label=None):
    app_list = _original_get_app_list(request, app_label=app_label)
    mega_models = {
        "MutolaaStatSnapshot",
        "MutolaaMahallaStat",
        "MutolaaMahallaAlias",
        "UstozAiStatSnapshot",
        "UstozAiMahallaStat",
        "UstozAiMahallaAlias",
        # kelgusida qo'shiladigan mega loyihalar modellari shu yerga tushadi
        "UzchessStatSnapshot",
        "UzchessMahallaStat",
        "UzchessMahallaAlias",
        "QizlarAkademiyasiStatSnapshot",
        "QizlarAkademiyasiMahallaStat",
        "QizlarAkademiyasiMahallaAlias",
    }
    task_models = {
        "TaskGroup",
        "Task",
        "TaskResponse",
        "TaskNotification",
    }

    mega_group = {
        "name": "Mega loyihalar",
        "app_label": "mega_loyihalar",
        "app_url": "",
        "has_module_perms": True,
        "models": [],
    }
    tasks_group = {
        "name": "Topshiriqlar",
        "app_label": "tasks",
        "app_url": "",
        "has_module_perms": True,
        "models": [],
    }

    new_app_list = []
    for app in app_list:
        remaining = []
        for model in app.get("models", []):
            if model.get("object_name") in mega_models:
                mega_group["models"].append(model)
            elif model.get("object_name") in task_models:
                tasks_group["models"].append(model)
            else:
                remaining.append(model)
        if remaining:
            app["models"] = remaining
            new_app_list.append(app)

    if mega_group["models"]:
        mega_group["models"].sort(key=lambda m: m.get("name", ""))
        new_app_list.append(mega_group)

    if tasks_group["models"]:
        tasks_group["models"].sort(key=lambda m: m.get("name", ""))
        new_app_list.append(tasks_group)

    return new_app_list


admin.site.get_app_list = _mega_get_app_list
