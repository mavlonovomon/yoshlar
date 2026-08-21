import os
import re
import requests
import uuid
from collections import Counter, defaultdict
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db.models import BooleanField, Case, Count, Q, Sum, When
from django.db import transaction
from django.contrib.sessions.models import Session
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.html import escape, format_html_join, mark_safe

from beshtashabbus.models import FiveInitiativeEvent
from beshtashabbus.views_applications import (
    DEFAULT_ATTEMPTS,
    _format_phone_number,
    _get_captcha,
    _read_4_letters_from_png,
    _wait_before_next_attempt,
)
from ishsiz_yoshlar.models import UnemployedYouth
from migratsiya.models import MigrationYouth
from otaliq.models import OtaliqYouth
from reyd.models import RaidEvent

from .forms import UchrashuvForm, UserProfileForm, YoshForm
from .models import Mahalla, MaktabOquvchi, Uchrashuv, User, Yosh
from .view_helpers import apply_sorting, is_active_school_class, is_management_user, normalize_sort_params


ATHLETE_INFO_URL = "https://api.5tashabbus.uz/Account/GetAthleteInfoForRegistration"
FILE_GET_URL = "https://api.5tashabbus.uz/FileManage/Get"
ATHLETE_INFO_BASE_PARAMS = {
    "identityDocumentId": "2",
    "lang": "uz_latn",
    "initiativTypeId": "1",
}
PASSPORT_SUFFIXES = ("AA", "AB", "AC", "AD", "AE", "FA", "FS")


def _request_with_proxy_fallback(method: str, url: str, session=None, **kwargs):
    session = session or requests.Session()
    try:
        return session.request(method, url, **kwargs)
    except requests.exceptions.ProxyError:
        session.trust_env = False
        return session.request(method, url, **kwargs)


def _extract_message(payload):
    if not isinstance(payload, dict):
        return str(payload)
    for key in ("message", "error", "detail"):
        value = payload.get(key)
        if value:
            return str(value)
    errors = payload.get("errors")
    if errors:
        return str(errors)
    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("message", "error", "detail"):
            value = result.get(key)
            if value:
                return str(value)
    return ""


def _parse_passport(passport_value):
    cleaned = re.sub(r"\s+", "", str(passport_value or "")).upper()
    if len(cleaned) < 3:
        return None, None
    series = cleaned[:2]
    number = "".join(ch for ch in cleaned[2:] if ch.isdigit())
    if len(series) != 2 or not series.isalpha() or not number:
        return None, None
    return series, number


def _school_document_type(series: str) -> str:
    series = (series or "").upper().strip()
    if not series:
        return ""
    return "Pasport" if any(series.endswith(suffix) for suffix in PASSPORT_SUFFIXES) else "Guvohnoma"


def _school_passport_q(field_name: str = "document_series"):
    query = Q()
    for suffix in PASSPORT_SUFFIXES:
        query |= Q(**{f"{field_name}__iendswith": suffix})
    return query


def _normalize_school_value(value):
    return re.sub(r"\s+", "", str(value or "").strip().casefold())


def _active_school_class_q(field_name: str):
    return Q(**{f"{field_name}__gt": ""}) & ~Q(**{f"{field_name}__in": ["-", "—", "–"]})


def _build_school_affinity_index():
    index = {
        "org": defaultdict(Counter),
        "org_region": defaultdict(Counter),
        "org_region_class": defaultdict(Counter),
    }
    rows = (
        Yosh.objects.select_related("mahalla")
        .filter(mahalla__isnull=False)
        .exclude(school_organization="")
        .filter(_active_school_class_q("school_class"))
        .values("school_organization", "school_organization_region", "school_class", "mahalla__name")
        .annotate(total=Count("id"))
    )
    for row in rows:
        mahalla_name = row["mahalla__name"] or "Noma'lum"
        org = _normalize_school_value(row["school_organization"])
        region = _normalize_school_value(row["school_organization_region"])
        klass = _normalize_school_value(row["school_class"])
        total = int(row["total"] or 0)
        if not org or total <= 0:
            continue
        index["org"][org][mahalla_name] += total
        if region:
            index["org_region"][(org, region)][mahalla_name] += total
        if region and klass:
            index["org_region_class"][(org, region, klass)][mahalla_name] += total
    return index


def _school_probability_payload(item, index):
    empty_html = mark_safe("<div class='small text-muted'>Hozircha ishonchli ehtimol topilmadi.</div>")
    org = _normalize_school_value(item.organization)
    region = _normalize_school_value(item.organization_region)
    klass = _normalize_school_value(item.klass)

    counters = [
        ("Tashkilot + hudud + sinf", index["org_region_class"].get((org, region, klass))),
        ("Tashkilot + hudud", index["org_region"].get((org, region))),
        ("Tashkilot", index["org"].get(org)),
    ]

    scope_label = ""
    counter = None
    for label, candidate in counters:
        if candidate:
            scope_label = label
            counter = candidate
            break

    if not counter:
        return {
            "scope_label": "",
            "html": empty_html,
            "items": [],
        }

    total = sum(counter.values())
    if total <= 0:
        return {
            "scope_label": scope_label,
            "html": empty_html,
            "items": [],
        }

    top_items = []
    rows = []
    for mahalla_name, count in counter.most_common(5):
        percent = round((count / total) * 100, 1)
        top_items.append({
            "name": mahalla_name,
            "count": count,
            "percent": percent,
        })
        rows.append((escape(mahalla_name), percent))

    rows_html = format_html_join(
        "",
        "<div class='d-flex justify-content-between gap-2'><span>{}</span><strong>{}%</strong></div>",
        rows,
    )
    html = mark_safe(
        "<div class='small'><div class='fw-semibold mb-1'>Ehtimoliy mahallalar</div>"
        f"{rows_html}"
        f"<div class='text-muted mt-1'>Asos: {escape(scope_label)}</div></div>"
    )
    return {
        "scope_label": scope_label,
        "html": html,
        "items": top_items,
    }


def _get_online_users(limit: int = 20):
    timeout_seconds = int(
        getattr(
            settings,
            "SESSION_IDLE_TIMEOUT",
            getattr(settings, "SESSION_COOKIE_AGE", 1800),
        )
    )
    if timeout_seconds <= 0:
        return []

    now_ts = int(timezone.now().timestamp())
    active_sessions = Session.objects.filter(expire_date__gt=timezone.now()).only("session_data", "expire_date")

    per_user = {}
    session_counts = {}

    for session in active_sessions:
        try:
            data = session.get_decoded()
        except Exception:
            continue

        user_id = data.get("_auth_user_id")
        last_activity_raw = data.get("_last_activity_ts")
        if not user_id or last_activity_raw is None:
            continue

        try:
            last_activity_ts = int(last_activity_raw)
        except (TypeError, ValueError):
            continue

        if now_ts - last_activity_ts > timeout_seconds:
            continue

        try:
            user_id_int = int(user_id)
        except (TypeError, ValueError):
            continue

        session_counts[user_id_int] = session_counts.get(user_id_int, 0) + 1
        current = per_user.get(user_id_int)
        if current is None or last_activity_ts > current["last_activity_ts"]:
            per_user[user_id_int] = {
                "last_activity_ts": last_activity_ts,
            }

    if not per_user:
        return []

    users = (
        User.objects.select_related("mahalla")
        .filter(id__in=per_user.keys())
        .order_by("full_name", "username")
    )

    online_users = []
    for user in users:
        item = per_user.get(user.id)
        if not item:
            continue
        user.online_last_activity = datetime.fromtimestamp(
            item["last_activity_ts"],
            tz=timezone.get_current_timezone(),
        )
        user.online_session_count = session_counts.get(user.id, 1)
        online_users.append(user)

    online_users.sort(key=lambda u: u.online_last_activity, reverse=True)
    return online_users[:limit]


@login_required
def dashboard(request):
    user = request.user
    context = {}
    can_view_online_users = is_management_user(user)

    if can_view_online_users:
        qs = Yosh.objects.all()
        meetings = Uchrashuv.objects.select_related("yosh", "yetakchi", "yosh__mahalla").all().order_by("-meeting_date")[:10]
        total_meetings_count = Uchrashuv.objects.count()
    else:
        qs = Yosh.objects.filter(mahalla=user.mahalla)
        meetings = (
            Uchrashuv.objects.select_related("yosh", "yetakchi", "yosh__mahalla")
            .filter(yosh__mahalla=user.mahalla)
            .order_by("-meeting_date")[:10]
        )
        total_meetings_count = Uchrashuv.objects.filter(yosh__mahalla=user.mahalla).count()

    context["total_yosh"] = qs.count()
    context["suhbat_bor"] = qs.annotate(has_meeting=Count("uchrashuvlar")).filter(has_meeting__gt=0).count()
    context["suhbat_yoq"] = context["total_yosh"] - context["suhbat_bor"]
    context["total_meetings"] = total_meetings_count

    if can_view_online_users:
        unemployed_qs = UnemployedYouth.objects.all()
        otaliq_qs = OtaliqYouth.objects.all()
        migration_qs = MigrationYouth.objects.all()
        reyd_qs = RaidEvent.objects.all()
        besh_qs = FiveInitiativeEvent.objects.all()
    else:
        unemployed_qs = UnemployedYouth.objects.filter(yosh__mahalla=user.mahalla)
        otaliq_qs = OtaliqYouth.objects.filter(yosh__mahalla=user.mahalla)
        migration_qs = MigrationYouth.objects.filter(yosh__mahalla=user.mahalla)
        reyd_qs = RaidEvent.objects.filter(mahalla=user.mahalla)
        besh_qs = FiveInitiativeEvent.objects.filter(mahalla=user.mahalla)

    context["module_summary"] = [
        {
            "title": "Ishsiz yoshlar",
            "value": unemployed_qs.count(),
            "icon": "bi-briefcase",
            "accent": "text-primary",
            "list_url": "ishsiz_yoshlar:list",
            "meta": f"Yordam berilgan: {unemployed_qs.filter(assistance__provided=True).count()}",
        },
        {
            "title": "Otaliqdagi yoshlar",
            "value": otaliq_qs.count(),
            "icon": "bi-shield-check",
            "accent": "text-success",
            "list_url": "otaliq:list",
            "meta": f"Suhbat o'tgan: {otaliq_qs.filter(meetings__isnull=False).distinct().count()}",
        },
        {
            "title": "Migratsiyadagi yoshlar",
            "value": migration_qs.count(),
            "icon": "bi-airplane",
            "accent": "text-info",
            "list_url": "migratsiya:list",
            "meta": f"Suhbat o'tgan: {migration_qs.filter(meetings__isnull=False).distinct().count()}",
        },
        {
            "title": "Reyd tadbirlari",
            "value": reyd_qs.count(),
            "icon": "bi-shield-exclamation",
            "accent": "text-warning",
            "list_url": "reyd:list",
            "meta": "Jinoyatchilik profilaktikasi",
        },
        {
            "title": "Besh tashabbus",
            "value": besh_qs.count(),
            "icon": "bi-award",
            "accent": "text-danger",
            "list_url": "beshtashabbus:list",
            "meta": f"Qamrov: {besh_qs.aggregate(total=Sum('coverage'))['total'] or 0}",
        },
    ]

    if can_view_online_users:
        context["show_online_users"] = True
        context["online_users"] = _get_online_users()
        context["online_users_count"] = len(context["online_users"])
    else:
        context["show_online_users"] = False
        context["online_users"] = []
        context["online_users_count"] = 0

    latest_meetings = list(meetings)
    for meeting in latest_meetings:
        if meeting.meeting_date:
            local_dt = timezone.localtime(meeting.meeting_date)
            meeting.meeting_date_str = local_dt.strftime("%d.%m.%Y")
            meeting.meeting_time_str = local_dt.strftime("%H:%M")
        else:
            meeting.meeting_date_str = ""
            meeting.meeting_time_str = ""
    context["latest_meetings"] = latest_meetings

    # Mahalla statistics for map
    mahalla_stats = []
    for mahalla in Mahalla.objects.all():
        yosh_count = Yosh.objects.filter(mahalla=mahalla).count()
        ishsiz_count = UnemployedYouth.objects.filter(yosh__mahalla=mahalla, is_deleted=False).count()
        migratsiya_count = MigrationYouth.objects.filter(yosh__mahalla=mahalla).count()
        otaliq_count = OtaliqYouth.objects.filter(yosh__mahalla=mahalla, is_deleted=False).count()
        suhbat_count = Uchrashuv.objects.filter(yosh__mahalla=mahalla).count()
        mahalla_stats.append({
            "id": mahalla.pk,
            "name": mahalla.name,
            "yosh_count": yosh_count,
            "ishsiz_count": ishsiz_count,
            "migratsiya_count": migratsiya_count,
            "otaliq_count": otaliq_count,
            "suhbat_count": suhbat_count,
        })

    context["mahalla_stats"] = mahalla_stats

    return render(request, "dashboard.html", context)


@login_required
def yosh_list(request):
    user = request.user
    mahallas = None

    if is_management_user(user):
        qs = Yosh.objects.all().order_by("fullname")
        mahallas = Mahalla.objects.all().order_by("name")

        mahalla_id = request.GET.get("mahalla")
        if mahalla_id:
            qs = qs.filter(mahalla_id=mahalla_id)
    else:
        qs = Yosh.objects.filter(mahalla=user.mahalla).order_by("fullname")

    q = request.GET.get("q")
    if q:
        q = q.strip()
        use_wildcard = ("*" in q) or ("?" in q)
        if use_wildcard:
            pattern = re.escape(q).replace(r"\*", ".*").replace(r"\?", ".")
            fullname_q = Q(fullname__iregex=f".*{pattern}.*")
            q_plain = q.replace("*", "").replace("?", "").strip()
        else:
            fullname_q = Q(fullname__icontains=q)
            q_plain = q

        full_q = fullname_q
        if q_plain:
            full_q = (
                full_q
                | Q(phone_number__icontains=q_plain)
                | Q(passport_number__icontains=q_plain)
                | Q(guvohnoma_raqami__icontains=q_plain)
                | Q(jshshir__icontains=q_plain)
                | Q(birth_date__icontains=q_plain)
            )

        qs = qs.filter(full_q)

    qs = (
        qs.select_related("mahalla", "unemployed_profile", "unemployed_profile__assistance")
        .prefetch_related("mahalla__leaders")
        .annotate(meeting_count=Count("uchrashuvlar", distinct=True))
        .annotate(
            has_meeting=Case(
                When(Q(meeting_count__gt=0), then=True),
                default=False,
                output_field=BooleanField(),
            )
        )
    )

    status = request.GET.get("status")
    if status == "bor":
        qs = qs.filter(meeting_count__gt=0)
    elif status == "yoq":
        qs = qs.filter(meeting_count=0)

    sort_field, sort_direction = normalize_sort_params(
        request,
        {
            "fullname",
            "birth_date",
            "mahalla",
            "phone_number",
            "passport_number",
            "guvohnoma_raqami",
            "school_organization",
            "school_class",
            "jshshir",
            "meeting_count",
            "has_meeting",
        },
        "fullname",
    )
    sort_map = {
        "fullname": "fullname",
        "birth_date": "birth_date",
        "mahalla": "mahalla__name",
        "phone_number": "phone_number",
        "passport_number": "passport_number",
        "guvohnoma_raqami": "guvohnoma_raqami",
        "school_organization": "school_organization",
        "school_class": "school_class",
        "jshshir": "jshshir",
        "meeting_count": "meeting_count",
        "has_meeting": ("meeting_count", "fullname"),
    }
    qs = apply_sorting(qs, sort_field, sort_direction, sort_map, "fullname")

    per_page = request.GET.get("per_page", "20")
    if per_page not in ["10", "20", "50", "100", "200"]:
        per_page = "20"

    paginator = Paginator(qs, int(per_page))
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "per_page": per_page,
        "mahallas": mahallas,
        "selected_mahalla": int(request.GET.get("mahalla"))
        if request.GET.get("mahalla") and request.GET.get("mahalla").isdigit()
        else None,
        "selected_status": request.GET.get("status"),
        "sort_field": sort_field,
        "sort_direction": sort_direction,
    }
    return render(request, "list.html", context)


@login_required
def maktab_oquvchi_list(request):
    q = (request.GET.get("q") or "").strip()
    organization = (request.GET.get("organization") or "").strip()
    klass = (request.GET.get("klass") or "").strip()
    doc_type = (request.GET.get("doc_type") or "").strip()
    user = request.user

    qs = Yosh.objects.select_related("mahalla").filter(
        Q(school_external_id__isnull=False)
        | Q(school_organization__gt="")
        | Q(school_class__gt="")
        | Q(school_document_number__gt="")
    )
    qs = qs.filter(_active_school_class_q("school_class"))

    if not is_management_user(user):
        if getattr(user, "mahalla", None):
            qs = qs.filter(mahalla=user.mahalla)
        else:
            qs = qs.none()

    if q:
        qs = qs.filter(
            Q(fullname__icontains=q)
            | Q(jshshir__icontains=q)
            | Q(passport_number__icontains=q)
            | Q(guvohnoma_raqami__icontains=q)
            | Q(school_organization__icontains=q)
            | Q(school_class__icontains=q)
            | Q(school_document_series__icontains=q)
            | Q(school_document_number__icontains=q)
            | Q(school_organization_region__icontains=q)
        )
    if organization:
        qs = qs.filter(school_organization__icontains=organization)
    if klass:
        qs = qs.filter(school_class__icontains=klass)
    passport_suffixes = ("AA", "AB", "AC", "AD", "AE", "FA", "FS")
    passport_q = Q()
    for suffix in passport_suffixes:
        passport_q |= Q(school_document_series__iendswith=suffix)
    if doc_type == "passport":
        qs = qs.filter(passport_q)
    elif doc_type == "guvohnoma":
        qs = qs.exclude(passport_q).filter(school_document_series__gt="")

    sort_field, sort_direction = normalize_sort_params(
        request,
        {
            "fullname",
            "jshshir",
            "birth_date",
            "mahalla",
            "organization",
            "organization_region",
            "klass",
            "document_series",
            "document_number",
        },
        "fullname",
    )
    sort_map = {
        "fullname": "fullname",
        "jshshir": "jshshir",
        "birth_date": "birth_date",
        "mahalla": "mahalla__name",
        "organization": "school_organization",
        "organization_region": "school_organization_region",
        "klass": "school_class",
        "document_series": "school_document_series",
        "document_number": "school_document_number",
    }
    qs = apply_sorting(qs, sort_field, sort_direction, sort_map, "fullname")

    per_page = request.GET.get("per_page", "20")
    if per_page not in ["10", "20", "50", "100", "200"]:
        per_page = "20"

    paginator = Paginator(qs, int(per_page))
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "per_page": per_page,
        "q": q,
        "organization": organization,
        "klass": klass,
        "doc_type": doc_type,
        "total_count": qs.count(),
        "passport_count": qs.filter(passport_q).count(),
        "guvohnoma_count": qs.exclude(passport_q).filter(school_document_series__gt="").count(),
        "sort_field": sort_field,
        "sort_direction": sort_direction,
    }
    return render(request, "maktab_oquvchilar/list.html", context)


@login_required
def maktab_oquvchi_pending_list(request):
    q = (request.GET.get("q") or "").strip()
    organization = (request.GET.get("organization") or "").strip()
    klass = (request.GET.get("klass") or "").strip()
    doc_type = (request.GET.get("doc_type") or "").strip()

    qs = MaktabOquvchi.objects.filter(linked_yosh__isnull=True)

    if q:
        qs = qs.filter(
            Q(fullname__icontains=q)
            | Q(pinfl__icontains=q)
            | Q(organization__icontains=q)
            | Q(klass__icontains=q)
            | Q(document_series__icontains=q)
            | Q(document_number__icontains=q)
            | Q(organization_region__icontains=q)
        )
    if organization:
        qs = qs.filter(organization__icontains=organization)
    if klass:
        qs = qs.filter(klass__icontains=klass)
    qs = qs.filter(_active_school_class_q("klass"))
    passport_q = _school_passport_q()
    if doc_type == "passport":
        qs = qs.filter(passport_q)
    elif doc_type == "guvohnoma":
        qs = qs.exclude(passport_q)

    sort_field, sort_direction = normalize_sort_params(
        request,
        {
            "fullname",
            "pinfl",
            "birth_date",
            "organization",
            "organization_region",
            "klass",
            "document_series",
            "document_number",
        },
        "fullname",
    )
    sort_map = {
        "fullname": "fullname",
        "pinfl": "pinfl",
        "birth_date": "birth_date",
        "organization": "organization",
        "organization_region": "organization_region",
        "klass": "klass",
        "document_series": "document_series",
        "document_number": "document_number",
    }
    qs = apply_sorting(qs, sort_field, sort_direction, sort_map, "fullname")

    per_page = request.GET.get("per_page", "20")
    if per_page not in ["10", "20", "50", "100", "200"]:
        per_page = "20"

    paginator = Paginator(qs, int(per_page))
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    affinity_index = _build_school_affinity_index()
    page_items = list(page_obj.object_list)
    for item in page_items:
        probability = _school_probability_payload(item, affinity_index)
        item.school_probability_html = probability["html"]
        item.school_probability_items = probability["items"]
        item.school_probability_scope = probability["scope_label"]
    page_obj.object_list = page_items

    show_assign_action = not is_management_user(request.user) and bool(getattr(request.user, "mahalla", None))

    context = {
        "page_obj": page_obj,
        "per_page": per_page,
        "q": q,
        "organization": organization,
        "klass": klass,
        "doc_type": doc_type,
        "total_count": qs.count(),
        "passport_count": qs.filter(passport_q).count(),
        "guvohnoma_count": qs.exclude(passport_q).count(),
        "can_assign": show_assign_action,
        "current_mahalla": getattr(getattr(request.user, "mahalla", None), "name", ""),
        "sort_field": sort_field,
        "sort_direction": sort_direction,
    }
    return render(request, "maktab_oquvchilar/unassigned_list.html", context)


@login_required
def maktab_oquvchi_assign(request, pk):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method noto'g'ri."}, status=405)

    user = request.user
    if not getattr(user, "mahalla", None):
        payload = {"success": False, "error": "Sizning mahallangiz biriktirilmagan."}
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(payload, status=400)
        messages.error(request, payload["error"])
        return redirect("maktab_oquvchi_pending_list")

    item = get_object_or_404(MaktabOquvchi, pk=pk, linked_yosh__isnull=True)
    if not is_active_school_class(item.klass):
        payload = {"success": False, "error": "Bu yozuv faol o'quvchi emas."}
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(payload, status=400)
        messages.error(request, payload["error"])
        return redirect("maktab_oquvchi_pending_list")
    doc_type = _school_document_type(item.document_series)
    doc_value = f"{item.document_series}{item.document_number}".strip()

    with transaction.atomic():
        yosh = Yosh.objects.filter(jshshir=item.pinfl).select_for_update().first()
        if not yosh:
            yosh = Yosh(
                fullname=item.fullname,
                birth_date=item.birth_date,
                jshshir=item.pinfl,
                address=item.organization_region or item.organization or item.fullname,
                mahalla=user.mahalla,
            )
        else:
            yosh.mahalla = user.mahalla

        yosh.school_external_id = item.external_id
        yosh.school_gender = item.gender
        yosh.school_nationality = item.nationality
        yosh.school_citizenship = item.citizenship
        yosh.school_document_series = item.document_series
        yosh.school_document_number = item.document_number
        yosh.school_organization = item.organization
        yosh.school_organization_region = item.organization_region
        yosh.school_class = item.klass
        yosh.school_imported_at = timezone.now()

        if doc_value:
            if doc_type == "Pasport":
                yosh.passport_number = yosh.passport_number or doc_value
            else:
                yosh.guvohnoma_raqami = yosh.guvohnoma_raqami or doc_value

        yosh.save()
        item.delete()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {
                "success": True,
                "pk": pk,
                "doc_type": doc_type,
                "message": "O'quvchi sizning mahallangizga biriktirildi.",
            }
        )

    next_url = (request.POST.get("next") or "").strip()
    messages.success(request, "O'quvchi sizning mahallangizga biriktirildi.")
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("maktab_oquvchi_pending_list")


@login_required
def yosh_detail(request, pk=None):
    user = request.user
    if pk:
        yosh = get_object_or_404(Yosh, pk=pk)
        if not is_management_user(user) and yosh.mahalla != user.mahalla:
            return render(request, "403.html", {"message": "Sizga bu anketa huquqi berilmagan"})
    else:
        yosh = None

    meetings = yosh.uchrashuvlar.all().order_by("-meeting_date") if yosh else []

    if request.method == "POST":
        form = YoshForm(request.POST, request.FILES, instance=yosh, user=user)
        if form.is_valid():
            new_yosh = form.save(commit=False)
            if not is_management_user(user):
                new_yosh.mahalla = user.mahalla
            else:
                new_yosh.mahalla = form.cleaned_data.get("mahalla")

            if not new_yosh.mahalla:
                messages.error(request, "Mahalla tanlanishi shart.")
                return render(request, "form.html", {"form": form, "yosh": yosh, "meetings": meetings})

            new_yosh.save()

            text = (form.cleaned_data.get("conversation_text") or "").strip()
            photo = form.cleaned_data.get("conversation_photo")
            if text or photo:
                Uchrashuv.objects.create(
                    yosh=new_yosh,
                    yetakchi=user,
                    meeting_date=timezone.now(),
                    conversation_text=text or "Suhbat rasmi yuklandi.",
                    photo=photo,
                )
            return redirect("yosh_list")
    else:
        form = YoshForm(instance=yosh, user=user)

    readonly = request.GET.get("readonly") == "true"

    return render(
        request,
        "form.html",
        {
            "form": form,
            "yosh": yosh,
            "meetings": meetings,
            "readonly": readonly,
        },
    )


@login_required
def meeting_edit(request, pk):
    meeting = get_object_or_404(Uchrashuv, pk=pk)
    user = request.user
    if not is_management_user(user) and meeting.yetakchi != user and meeting.yosh.mahalla != user.mahalla:
        return redirect("dashboard")

    if request.method == "POST":
        form = UchrashuvForm(request.POST, request.FILES, instance=meeting)
        if form.is_valid():
            form.save()
            return redirect("yosh_detail", pk=meeting.yosh.pk)
    else:
        form = UchrashuvForm(instance=meeting)

    return render(request, "meeting_form.html", {"form": form, "meeting": meeting})


def info_view(request):
    return render(request, "info.html")


@login_required
def user_profile(request):
    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Anketa ma'lumotlari saqlandi.")
            return redirect("user_profile")
        messages.error(request, "Iltimos, formadagi xatolarni to'g'rilang.")
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, "profile.html", {"form": form})


@login_required
def user_list(request):
    if not is_management_user(request.user):
        messages.error(request, "Bu bo'lim faqat Super Admin yoki Rahbar uchun.")
        return redirect("dashboard")

    sort_field, sort_direction = normalize_sort_params(
        request,
        {"full_name", "username", "role", "pinfl", "phone_number", "mahalla", "sector"},
        "full_name",
    )
    sort_map = {
        "full_name": "full_name",
        "username": "username",
        "role": "role",
        "pinfl": "pinfl",
        "phone_number": "phone_number",
        "mahalla": "mahalla__name",
        "sector": "sector",
    }
    users = apply_sorting(User.objects.select_related("mahalla").all(), sort_field, sort_direction, sort_map, "full_name")

    q = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "").strip()

    if q:
        users = users.filter(
            Q(full_name__icontains=q)
            | Q(username__icontains=q)
            | Q(pinfl__icontains=q)
            | Q(phone_number__icontains=q)
            | Q(mahalla__name__icontains=q)
        )
    if role in {"SUPER_ADMIN", "RAHBAR", "YETAKCHI"}:
        users = users.filter(role=role)

    context = {
        "users": users,
        "q": q,
        "selected_role": role,
        "sort_field": sort_field,
        "sort_direction": sort_direction,
    }
    return render(request, "users/list.html", context)


@login_required
def yosh_refresh_photo(request, pk):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method noto'g'ri."}, status=405)

    yosh = get_object_or_404(Yosh, pk=pk)
    user = request.user
    if not is_management_user(user) and yosh.mahalla != user.mahalla:
        return JsonResponse({"success": False, "error": "Ruxsat yo'q."}, status=403)

    document_series, document_number = _parse_passport(yosh.passport_number)
    if not document_series or not document_number:
        return JsonResponse({"success": False, "error": "Pasport seriya/raqami noto'g'ri."}, status=400)

    if not yosh.birth_date:
        return JsonResponse({"success": False, "error": "Tug'ilgan sana bazada topilmadi."}, status=400)

    phone_number = _format_phone_number(yosh.phone_number)
    if not phone_number:
        return JsonResponse({"success": False, "error": "Telefon raqam formati noto'g'ri."}, status=400)

    session = requests.Session()
    request_id = uuid.uuid4().hex.upper()
    last_error = "Captcha olinmadi."
    athlete_result = None

    for attempt in range(1, DEFAULT_ATTEMPTS + 1):
        captcha_json, captcha_error = _get_captcha(phone_number, session=session, request_id=request_id)
        if captcha_error:
            last_error = captcha_error
        if not captcha_json:
            _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
            continue

        captcha_b64 = captcha_json.get("captcha") or captcha_json.get("result")
        if not captcha_b64:
            last_error = f"Sayt xatoligi (captcha): captcha topilmadi: {captcha_json}"
            _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
            continue

        try:
            captcha_text = _read_4_letters_from_png(captcha_b64)
        except Exception as exc:
            last_error = f"Captcha o'qishda xatolik: {exc}"
            _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
            continue

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "X-Request-Id": request_id,
        }
        params = dict(ATHLETE_INFO_BASE_PARAMS)
        params.update(
            {
                "identityDocumentId": "2",
                "DocumentSeries": document_series,
                "DocumentNumber": document_number,
                "DateOfBirth": yosh.birth_date.strftime("%d.%m.%Y"),
                "captchaText": captcha_text,
                "phoneNumber": phone_number,
            }
        )

        try:
            response = _request_with_proxy_fallback(
                "POST",
                ATHLETE_INFO_URL,
                headers=headers,
                data=params,
                session=session,
                timeout=15,
            )
            try:
                athlete_info = response.json()
            except ValueError:
                response.raise_for_status()
                last_error = "GetAthleteInfo javobi JSON emas"
                _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                continue
        except requests.exceptions.RequestException as e:
            last_error = f"Internet xatoligi (GetAthleteInfo): {e}"
            _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
            continue

        if response.status_code >= 400 and isinstance(athlete_info, dict):
            last_error = _extract_message(athlete_info) or "GetAthleteInfo xatoligi."
            _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
            continue

        if not athlete_info or athlete_info.get("success") is not True:
            last_error = _extract_message(athlete_info) or "GetAthleteInfo xatoligi."
            _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
            continue

        athlete_result = athlete_info.get("result")
        if not isinstance(athlete_result, dict):
            last_error = "GetAthleteInfo natijasi noto'g'ri."
            _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
            continue

        break

    if athlete_result is None:
        return JsonResponse({"success": False, "error": last_error}, status=400)

    photo = athlete_result.get("photo") if isinstance(athlete_result.get("photo"), dict) else {}
    attachment_file_id = photo.get("attachmentfileid")
    if not attachment_file_id:
        return JsonResponse({"success": False, "error": "Pasport rasmi topilmadi."}, status=404)

    try:
        file_response = _request_with_proxy_fallback(
            "GET",
            FILE_GET_URL,
            headers=headers,
            params={"id": attachment_file_id},
            timeout=20,
        )
        file_response.raise_for_status()
        image_bytes = file_response.content
    except requests.exceptions.RequestException as e:
        return JsonResponse({"success": False, "error": f"Internet xatoligi (FileManage): {e}"}, status=502)

    if not image_bytes:
        return JsonResponse({"success": False, "error": "Rasm yuklab bo'lmadi."}, status=502)

    filename = str(attachment_file_id).split("/")[-1]
    if "." not in filename:
        filename = f"{filename}.jpg"
    yosh.photo.save(filename, ContentFile(image_bytes), save=True)

    return JsonResponse({"success": True, "photo_url": yosh.photo.url})


@login_required
def yosh_bulk_refresh_photos(request):
    if not is_management_user(request.user):
        messages.error(request, "Bu bo'lim faqat Super Admin yoki Rahbar uchun.")
        return redirect("dashboard")

    if request.method != "POST":
        return render(request, "bulk_refresh.html", {"total": 0})

    year = int(request.POST.get("year", 2026))
    only_no_photo = request.POST.get("only_no_photo") == "on"
    youths = UnemployedYouth.objects.filter(year=year).select_related("yosh").order_by("id")
    if only_no_photo:
        youths = youths.filter(yosh__photo__isnull=True) | youths.filter(yosh__photo="")
    total = youths.count()

    import time as _time
    import json

    def generate():
        updated = 0
        errors = 0

        yield "data: " + json.dumps({"type": "start", "total": total, "year": year}) + "\n\n"

        for idx, uy in enumerate(youths, 1):
            yosh = uy.yosh
            fio = yosh.fullname or "ID-{}".format(yosh.pk)

            document_series, document_number = _parse_passport(yosh.passport_number)
            if not document_series or not document_number:
                errors += 1
                msg = "Pasport noto'g'ri"
                yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "error", "msg": msg}) + "\n\n"
                if idx < total:
                    _time.sleep(12)
                continue

            if not yosh.birth_date:
                errors += 1
                msg = "Tug'ilgan sana yo'q"
                yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "error", "msg": msg}) + "\n\n"
                if idx < total:
                    _time.sleep(12)
                continue

            phone_number = _format_phone_number(yosh.phone_number)
            if not phone_number:
                errors += 1
                msg = "Telefon raqam noto'g'ri"
                yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "error", "msg": msg}) + "\n\n"
                if idx < total:
                    _time.sleep(12)
                continue

            session = requests.Session()
            request_id = uuid.uuid4().hex.upper()
            last_error = "Captcha olinmadi."
            athlete_result = None

            for attempt in range(1, DEFAULT_ATTEMPTS + 1):
                captcha_json, captcha_error = _get_captcha(phone_number, session=session, request_id=request_id)
                if captcha_error:
                    last_error = captcha_error
                if not captcha_json:
                    _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                    continue

                captcha_b64 = captcha_json.get("captcha") or captcha_json.get("result")
                if not captcha_b64:
                    last_error = "Captcha topilmadi"
                    _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                    continue

                try:
                    captcha_text = _read_4_letters_from_png(captcha_b64)
                except Exception as exc:
                    last_error = "Captcha o'qishda xatolik: {}".format(exc)
                    _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                    continue

                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "X-Request-Id": request_id,
                }
                params = dict(ATHLETE_INFO_BASE_PARAMS)
                params.update({
                    "identityDocumentId": "2",
                    "DocumentSeries": document_series,
                    "DocumentNumber": document_number,
                    "DateOfBirth": yosh.birth_date.strftime("%d.%m.%Y"),
                    "captchaText": captcha_text,
                    "phoneNumber": phone_number,
                })

                try:
                    response = _request_with_proxy_fallback(
                        "POST", ATHLETE_INFO_URL, headers=headers,
                        data=params, session=session, timeout=15,
                    )
                    try:
                        athlete_info = response.json()
                    except ValueError:
                        response.raise_for_status()
                        last_error = "Javob JSON emas"
                        _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                        continue
                except requests.exceptions.RequestException as e:
                    last_error = "Internet xatoligi: {}".format(e)
                    _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                    continue

                if response.status_code >= 400 and isinstance(athlete_info, dict):
                    last_error = _extract_message(athlete_info) or "API xatoligi"
                    _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                    continue

                if not athlete_info or athlete_info.get("success") is not True:
                    last_error = _extract_message(athlete_info) or "API xatoligi"
                    _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                    continue

                athlete_result = athlete_info.get("result")
                if not isinstance(athlete_result, dict):
                    last_error = "Natija noto'g'ri"
                    _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                    continue

                break

            if athlete_result is None:
                errors += 1
                yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "error", "msg": last_error}) + "\n\n"
                if idx < total:
                    _time.sleep(12)
                continue

            photo = athlete_result.get("photo") if isinstance(athlete_result.get("photo"), dict) else {}
            attachment_file_id = photo.get("attachmentfileid")
            if not attachment_file_id:
                errors += 1
                msg = "Rasm topilmadi"
                yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "error", "msg": msg}) + "\n\n"
                if idx < total:
                    _time.sleep(12)
                continue

            try:
                file_response = _request_with_proxy_fallback(
                    "GET", FILE_GET_URL, headers=headers,
                    params={"id": attachment_file_id}, timeout=20,
                )
                file_response.raise_for_status()
                image_bytes = file_response.content
            except requests.exceptions.RequestException as e:
                errors += 1
                msg = "Rasm yuklab bo'lmadi: {}".format(e)
                yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "error", "msg": msg}) + "\n\n"
                if idx < total:
                    _time.sleep(12)
                continue

            if not image_bytes:
                errors += 1
                msg = "Rasm bo'sh"
                yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "error", "msg": msg}) + "\n\n"
                if idx < total:
                    _time.sleep(12)
                continue

            filename = str(attachment_file_id).split("/")[-1]
            if "." not in filename:
                filename = "{}.jpg".format(filename)
            yosh.photo.save(filename, ContentFile(image_bytes), save=True)
            updated += 1

            yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "ok", "msg": "Yangilandi"}) + "\n\n"

            if idx < total:
                _time.sleep(12)

        yield "data: " + json.dumps({"type": "done", "total": total, "updated": updated, "errors": errors}) + "\n\n"

    return StreamingHttpResponse(generate(), content_type="text/event-stream")


@login_required
def yosh_all_bulk_refresh_photos(request):
    if not is_management_user(request.user):
        messages.error(request, "Bu bo'lim faqat Super Admin yoki Rahbar uchun.")
        return redirect("dashboard")

    if request.method != "POST":
        total_count = Yosh.objects.count()
        no_photo_count = Yosh.objects.filter(photo__isnull=True).count() + Yosh.objects.filter(photo='').count()
        missing_file_count = 0
        for y in Yosh.objects.exclude(photo__isnull=True).exclude(photo=''):
            try:
                if not y.photo or not os.path.exists(y.photo.path):
                    missing_file_count += 1
            except Exception:
                missing_file_count += 1
        no_photo_count += missing_file_count
        return render(request, "bulk_refresh_all.html", {"total": 0, "total_count": total_count, "no_photo_count": no_photo_count})

    only_no_photo = request.POST.get("only_no_photo") == "on"
    youths = Yosh.objects.all().order_by("id")
    if only_no_photo:
        # Get IDs of youths with photo file that actually exists
        valid_photo_ids = []
        for y in youths.exclude(photo__isnull=True).exclude(photo=''):
            try:
                if y.photo and os.path.exists(y.photo.path):
                    valid_photo_ids.append(y.pk)
            except Exception:
                pass
        youths = youths.exclude(pk__in=valid_photo_ids)
    total = youths.count()

    import time as _time
    import json

    def generate():
        updated = 0
        errors = 0

        yield "data: " + json.dumps({"type": "start", "total": total, "mode": "only_no_photo" if only_no_photo else "all"}) + "\n\n"

        for idx, yosh in enumerate(youths, 1):
            fio = yosh.fullname or "ID-{}".format(yosh.pk)

            document_series, document_number = _parse_passport(yosh.passport_number)
            if not document_series or not document_number:
                errors += 1
                msg = "Pasport noto'g'ri"
                yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "error", "msg": msg}) + "\n\n"
                if idx < total:
                    _time.sleep(12)
                continue

            if not yosh.birth_date:
                errors += 1
                msg = "Tug'ilgan sana yo'q"
                yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "error", "msg": msg}) + "\n\n"
                if idx < total:
                    _time.sleep(12)
                continue

            phone_number = _format_phone_number(yosh.phone_number)
            if not phone_number:
                errors += 1
                msg = "Telefon raqam noto'g'ri"
                yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "error", "msg": msg}) + "\n\n"
                if idx < total:
                    _time.sleep(12)
                continue

            session = requests.Session()
            request_id = uuid.uuid4().hex.upper()
            last_error = "Captcha olinmadi."
            athlete_result = None

            for attempt in range(1, DEFAULT_ATTEMPTS + 1):
                captcha_json, captcha_error = _get_captcha(phone_number, session=session, request_id=request_id)
                if captcha_error:
                    last_error = captcha_error
                if not captcha_json:
                    _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                    continue

                captcha_b64 = captcha_json.get("captcha") or captcha_json.get("result")
                if not captcha_b64:
                    last_error = "Captcha topilmadi"
                    _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                    continue

                try:
                    captcha_text = _read_4_letters_from_png(captcha_b64)
                except Exception as exc:
                    last_error = "Captcha o'qishda xatolik: {}".format(exc)
                    _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                    continue

                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "X-Request-Id": request_id,
                }
                params = dict(ATHLETE_INFO_BASE_PARAMS)
                params.update({
                    "identityDocumentId": "2",
                    "DocumentSeries": document_series,
                    "DocumentNumber": document_number,
                    "DateOfBirth": yosh.birth_date.strftime("%d.%m.%Y"),
                    "captchaText": captcha_text,
                    "phoneNumber": phone_number,
                })

                try:
                    response = _request_with_proxy_fallback(
                        "POST", ATHLETE_INFO_URL, headers=headers,
                        data=params, session=session, timeout=15,
                    )
                    try:
                        athlete_info = response.json()
                    except ValueError:
                        response.raise_for_status()
                        last_error = "Javob JSON emas"
                        _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                        continue
                except requests.exceptions.RequestException as e:
                    last_error = "Internet xatoligi: {}".format(e)
                    _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                    continue

                if response.status_code >= 400 and isinstance(athlete_info, dict):
                    last_error = _extract_message(athlete_info) or "API xatoligi"
                    _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                    continue

                if not athlete_info or athlete_info.get("success") is not True:
                    last_error = _extract_message(athlete_info) or "API xatoligi"
                    _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                    continue

                athlete_result = athlete_info.get("result")
                if not isinstance(athlete_result, dict):
                    last_error = "Natija noto'g'ri"
                    _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                    continue

                break

            if athlete_result is None:
                errors += 1
                yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "error", "msg": last_error}) + "\n\n"
                if idx < total:
                    _time.sleep(12)
                continue

            photo = athlete_result.get("photo") if isinstance(athlete_result.get("photo"), dict) else {}
            attachment_file_id = photo.get("attachmentfileid")
            if not attachment_file_id:
                errors += 1
                msg = "Rasm topilmadi"
                yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "error", "msg": msg}) + "\n\n"
                if idx < total:
                    _time.sleep(12)
                continue

            try:
                file_response = _request_with_proxy_fallback(
                    "GET", FILE_GET_URL, headers=headers,
                    params={"id": attachment_file_id}, timeout=20,
                )
                file_response.raise_for_status()
                image_bytes = file_response.content
            except requests.exceptions.RequestException as e:
                errors += 1
                msg = "Rasm yuklab bo'lmadi: {}".format(e)
                yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "error", "msg": msg}) + "\n\n"
                if idx < total:
                    _time.sleep(12)
                continue

            if not image_bytes:
                errors += 1
                msg = "Rasm bo'sh"
                yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "error", "msg": msg}) + "\n\n"
                if idx < total:
                    _time.sleep(12)
                continue

            filename = str(attachment_file_id).split("/")[-1]
            if "." not in filename:
                filename = "{}.jpg".format(filename)
            yosh.photo.save(filename, ContentFile(image_bytes), save=True)
            updated += 1

            yield "data: " + json.dumps({"type": "progress", "idx": idx, "total": total, "fio": fio, "status": "ok", "msg": "Yangilandi"}) + "\n\n"

            if idx < total:
                _time.sleep(12)

        yield "data: " + json.dumps({"type": "done", "total": total, "updated": updated, "errors": errors}) + "\n\n"

    return StreamingHttpResponse(generate(), content_type="text/event-stream")
