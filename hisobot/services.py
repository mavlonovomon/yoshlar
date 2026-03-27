from __future__ import annotations

import calendar
import json
import textwrap
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from beshtashabbus.models import (
    FiveInitiativeApplicationEntry,
    FiveInitiativeApplicationSnapshot,
    FiveInitiativeEvent,
)
from bilim_sinovi.models import Question, QuestionPackage, TestConfig, TestResult
from intizom_jazo.models import DisciplineAction
from ishsiz_yoshlar.models import AssistanceInfo, ResponsibleLeader, UnemployedYouth
from kredit_yo_naltirish.models import CreditCandidate
from migratsiya.models import MigrationMeeting, MigrationYouth
from otaliq.models import OtaliqAssistance, OtaliqLeader, OtaliqYouth
from reyd.models import RaidEvent, RaidPhoto
from yoqlama.models import AttendanceRecord, AttendanceSession


@dataclass(frozen=True)
class ReportPeriod:
    report_type: str
    year: int | None
    quarter: int | None
    half: int | None
    start_date: date
    end_date: date
    label: str
    date_range_label: str


def resolve_report_period(
    report_type: str,
    year: int | None = None,
    quarter: int | None = None,
    half: int | None = None,
    month: int | None = None,
    day_date: date | None = None,
    week_start: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> ReportPeriod:
    normalized_type = (report_type or "QUARTER").strip().upper()
    current_year = timezone.localdate().year
    selected_year = year or current_year

    if normalized_type == "DAY":
        selected_day = day_date or timezone.localdate()
        period_start = selected_day
        period_end = selected_day
        selected_year = selected_day.year
        quarter = None
        half = None
        month = None
        label = f"{selected_day.strftime('%d.%m.%Y')} (kunlik)"
    elif normalized_type == "WEEK":
        selected_week_start = week_start or timezone.localdate()
        period_start = selected_week_start
        period_end = selected_week_start + timedelta(days=6)
        selected_year = period_start.year
        quarter = None
        half = None
        month = None
        label = f"{period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')} (haftalik)"
    elif normalized_type == "MONTH":
        selected_month = month if month in set(range(1, 13)) else timezone.localdate().month
        end_day = calendar.monthrange(selected_year, selected_month)[1]
        period_start = date(selected_year, selected_month, 1)
        period_end = date(selected_year, selected_month, end_day)
        quarter = None
        half = None
        month = selected_month
        label = f"{selected_year}-yil {selected_month}-oy (oylik)"
    elif normalized_type in {"DATE_RANGE", "CUSTOM_RANGE", "CUSTOM"}:
        today = timezone.localdate()
        period_start = start_date or today.replace(day=1)
        period_end = end_date or today
        if period_start > period_end:
            period_start, period_end = period_end, period_start
        selected_year = period_end.year
        quarter = None
        half = None
        month = None
        normalized_type = "DATE_RANGE"
        label = "Tanlangan vaqt oraligi"
    elif normalized_type == "YEAR":
        start_month, end_month = 1, 12
        quarter = None
        half = None
        month = None
        label = f"{selected_year}-yil (yillik)"
    elif normalized_type == "HALF_YEAR":
        selected_half = half if half in {1, 2} else 1
        start_month = 1 if selected_half == 1 else 7
        end_month = 6 if selected_half == 1 else 12
        quarter = None
        half = selected_half
        month = None
        label = f"{selected_year}-yil {selected_half}-yarim yillik"
    else:
        normalized_type = "QUARTER"
        selected_quarter = quarter if quarter in {1, 2, 3, 4} else 1
        start_month = ((selected_quarter - 1) * 3) + 1
        end_month = start_month + 2
        quarter = selected_quarter
        half = None
        month = None
        label = f"{selected_year}-yil {selected_quarter}-kvartal"

    if normalized_type in {"DATE_RANGE", "DAY", "WEEK", "MONTH"}:
        range_label = f"{period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}"
        resolved_start_date = period_start
        resolved_end_date = period_end
    else:
        end_day = calendar.monthrange(selected_year, end_month)[1]
        resolved_start_date = date(selected_year, start_month, 1)
        resolved_end_date = date(selected_year, end_month, end_day)
        range_label = f"{resolved_start_date.strftime('%d.%m.%Y')} - {resolved_end_date.strftime('%d.%m.%Y')}"

    return ReportPeriod(
        report_type=normalized_type,
        year=selected_year,
        quarter=quarter,
        half=half,
        start_date=resolved_start_date,
        end_date=resolved_end_date,
        label=label,
        date_range_label=range_label,
    )


def _resolve_calculation_mode(period: ReportPeriod) -> tuple[str, date]:
    today = timezone.localdate()
    if period.report_type == "DATE_RANGE":
        return "DATE_RANGE", period.end_date
    if period.end_date >= today:
        return "LIVE_SVOD", today
    return "AS_OF_PERIOD_END", period.end_date


def _calculation_mode_label(mode: str) -> str:
    if mode == "DATE_RANGE":
        return "Tanlangan sana oralig'i bo'yicha"
    if mode == "LIVE_SVOD":
        return "Joriy svod (real vaqt holati)"
    return "Davr yakuni holati"


def _apply_scope(queryset, date_lookup: str, mode: str, period: ReportPeriod):
    if mode == "LIVE_SVOD":
        return queryset
    if mode == "DATE_RANGE":
        return queryset.filter(**{f"{date_lookup}__range": (period.start_date, period.end_date)})
    return queryset.filter(**{f"{date_lookup}__lte": period.end_date})


def _build_labeled_breakdown(
    count_map: dict,
    choices: list[tuple[str, str]],
    unknown_label_prefix: str,
    include_unspecified: bool = False,
) -> tuple[list[dict], int]:
    choice_map = {code: label for code, label in choices}
    ordered_codes = [code for code, _ in choices]
    remaining = dict(count_map)
    breakdown: list[dict] = []
    total = 0

    for code in ordered_codes:
        count = int(remaining.pop(code, 0) or 0)
        if count <= 0:
            continue
        breakdown.append({"code": code, "label": choice_map.get(code, code), "count": count})
        total += count

    for code, value in sorted(remaining.items(), key=lambda item: str(item[0])):
        count = int(value or 0)
        if count <= 0:
            continue
        if code in {None, ""}:
            continue
        breakdown.append(
            {
                "code": str(code),
                "label": f"{unknown_label_prefix} ({code})",
                "count": count,
            }
        )
        total += count

    if include_unspecified:
        unspecified_count = int(remaining.get(None, 0) or 0) + int(remaining.get("", 0) or 0)
        if unspecified_count > 0:
            breakdown.append({"code": "UNSPECIFIED", "label": "Aniqlanmagan toifa", "count": unspecified_count})
            total += unspecified_count

    return breakdown, total


def _build_text_breakdown(rows, label_key: str, count_key: str = "count", limit: int | None = 10) -> list[dict]:
    items = []
    for row in rows:
        count = int(row.get(count_key, 0) or 0)
        if count <= 0:
            continue
        label = str(row.get(label_key) or "Nomalum")
        items.append({"code": label, "label": label, "count": count})
    if limit is not None:
        items = items[:limit]
    return items


def _as_int(value) -> int:
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    return int(value)


def _as_number_display(value) -> str:
    if value is None:
        return "0"
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _module_report(
    *,
    key: str,
    title: str,
    total_label: str,
    total_value: int,
    covered_label: str | None = None,
    covered_value: int | None = None,
    covered_percent: float | None = None,
    secondary_metrics: list[dict] | None = None,
    breakdowns: list[dict] | None = None,
    summary: str | None = None,
    flat: dict | None = None,
) -> dict:
    return {
        "key": key,
        "title": title,
        "total_label": total_label,
        "total_value": int(total_value or 0),
        "covered_label": covered_label,
        "covered_value": covered_value if covered_value is None else int(covered_value),
        "covered_percent": covered_percent,
        "secondary_metrics": secondary_metrics or [],
        "breakdowns": breakdowns or [],
        "summary": summary or "",
        "flat": flat or {},
    }


def _assistance_filter(prefix: str, mode: str, period: ReportPeriod) -> Q:
    def lk(field: str) -> str:
        return f"{prefix}__{field}"

    provided = Q(**{lk("provided"): True})
    if mode == "LIVE_SVOD":
        return provided
    if mode == "DATE_RANGE":
        return provided & (
            Q(**{f"{lk('date_provided')}__range": (period.start_date, period.end_date)})
            | (
                Q(**{lk("date_provided"): None})
                & Q(**{f"{lk('created_at__date')}__range": (period.start_date, period.end_date)})
            )
        )
    return provided & (
        Q(**{f"{lk('date_provided')}__lte": period.end_date})
        | (Q(**{lk('date_provided'): None}) & Q(**{f"{lk('created_at__date')}__lte": period.end_date}))
    )


def _collect_ishsiz_module(period: ReportPeriod, mode: str) -> dict:
    if mode == "DATE_RANGE":
        base_qs = UnemployedYouth.objects.all()
    else:
        base_qs = _apply_scope(UnemployedYouth.objects.all(), "created_at__date", mode, period)

    assistance_filter = _assistance_filter("assistance", mode, period)
    total_youth = base_qs.count()
    assisted_count = base_qs.filter(assistance_filter).distinct().count()
    percent = round((assisted_count / total_youth) * 100, 1) if total_youth else 0.0

    if mode == "LIVE_SVOD":
        with_meeting_count = base_qs.filter(meetings__isnull=False).distinct().count()
    elif mode == "DATE_RANGE":
        with_meeting_count = base_qs.filter(
            meetings__meeting_date__date__range=(period.start_date, period.end_date)
        ).distinct().count()
    else:
        with_meeting_count = base_qs.filter(meetings__meeting_date__date__lte=period.end_date).distinct().count()

    assistance_rows = (
        base_qs.filter(assistance_filter)
        .values("assistance__assistance_type")
        .annotate(count=Count("id", distinct=True))
        .order_by("-count")
    )
    assistance_map = {row["assistance__assistance_type"]: row["count"] for row in assistance_rows}
    assistance_breakdown, _ = _build_labeled_breakdown(
        assistance_map,
        list(AssistanceInfo.ASSISTANCE_TYPES),
        unknown_label_prefix="Boshqa yordam turi",
        include_unspecified=True,
    )

    leader_rows = (
        ResponsibleLeader.objects.filter(assigned_youths__in=base_qs)
        .values("level")
        .annotate(count=Count("id", distinct=True))
        .order_by("-count")
    )
    leader_map = {row["level"]: row["count"] for row in leader_rows}
    leader_breakdown, leader_total = _build_labeled_breakdown(
        leader_map,
        list(ResponsibleLeader.LEVEL_CHOICES),
        unknown_label_prefix="Boshqa daraja",
    )

    category_rows = base_qs.values("category").annotate(count=Count("id")).order_by("-count")
    category_map = {row["category"]: row["count"] for row in category_rows}
    category_breakdown, _ = _build_labeled_breakdown(
        category_map,
        list(UnemployedYouth.CATEGORY_CHOICES),
        unknown_label_prefix="Boshqa toifa",
    )

    not_assisted = max(total_youth - assisted_count, 0)
    summary = (
        f"Jami {total_youth} nafar, yordam ko'rsatilgan {assisted_count} nafar ({percent}%). "
        f"Yordam ko'rsatilmagan {not_assisted} nafar."
    )

    return _module_report(
        key="ishsiz_yoshlar",
        title="Ishsiz yoshlar",
        total_label="Jami ishsiz yoshlar",
        total_value=total_youth,
        covered_label="Yordam ko'rsatilgan",
        covered_value=assisted_count,
        covered_percent=percent,
        secondary_metrics=[
            {"label": "Uchrashuv o'tkazilgan", "value": with_meeting_count},
            {"label": "Yordam ko'rsatilmagan", "value": not_assisted},
            {"label": "Biriktirilgan rahbarlar", "value": leader_total},
        ],
        breakdowns=[
            {"title": "Yordam yo'nalishlari", "items": assistance_breakdown},
            {"title": "Rahbarlar darajasi", "items": leader_breakdown},
            {"title": "Ishsizlik toifalari", "items": category_breakdown},
        ],
        summary=summary,
        flat={
            "total_youth": total_youth,
            "with_meeting_count": with_meeting_count,
            "assisted_count": assisted_count,
            "assisted_percent": percent,
            "not_assisted_count": not_assisted,
            "leader_total": leader_total,
            "leader_breakdown": leader_breakdown,
            "assistance_breakdown": assistance_breakdown,
            "youth_category_breakdown": category_breakdown,
        },
    )


def _collect_otaliq_module(period: ReportPeriod, mode: str) -> dict:
    if mode == "DATE_RANGE":
        base_qs = OtaliqYouth.objects.all()
    else:
        base_qs = _apply_scope(OtaliqYouth.objects.all(), "created_at__date", mode, period)

    assistance_filter = _assistance_filter("assistance", mode, period)
    total_youth = base_qs.count()
    assisted_count = base_qs.filter(assistance_filter).distinct().count()
    percent = round((assisted_count / total_youth) * 100, 1) if total_youth else 0.0

    if mode == "LIVE_SVOD":
        with_meeting_count = base_qs.filter(meetings__isnull=False).distinct().count()
    elif mode == "DATE_RANGE":
        with_meeting_count = base_qs.filter(
            meetings__meeting_date__date__range=(period.start_date, period.end_date)
        ).distinct().count()
    else:
        with_meeting_count = base_qs.filter(meetings__meeting_date__date__lte=period.end_date).distinct().count()

    assistance_rows = (
        base_qs.filter(assistance_filter)
        .values("assistance__assistance_type")
        .annotate(count=Count("id", distinct=True))
        .order_by("-count")
    )
    assistance_map = {row["assistance__assistance_type"]: row["count"] for row in assistance_rows}
    assistance_breakdown, _ = _build_labeled_breakdown(
        assistance_map,
        list(OtaliqAssistance.ASSISTANCE_TYPES),
        unknown_label_prefix="Boshqa yordam turi",
        include_unspecified=True,
    )

    leader_rows = (
        OtaliqLeader.objects.filter(assigned_youths__in=base_qs)
        .values("level")
        .annotate(count=Count("id", distinct=True))
        .order_by("-count")
    )
    leader_map = {row["level"]: row["count"] for row in leader_rows}
    leader_breakdown, leader_total = _build_labeled_breakdown(
        leader_map,
        list(OtaliqLeader.LEVEL_CHOICES),
        unknown_label_prefix="Boshqa daraja",
    )

    category_rows = base_qs.values("category").annotate(count=Count("id")).order_by("-count")
    category_map = {row["category"]: row["count"] for row in category_rows}
    category_breakdown, _ = _build_labeled_breakdown(
        category_map,
        list(OtaliqYouth.CATEGORY_CHOICES),
        unknown_label_prefix="Boshqa toifa",
    )

    summary = (
        f"Jami {total_youth} nafar, yordam ko'rsatilgan {assisted_count} nafar ({percent}%). "
        f"Uchrashuv o'tkazilgan {with_meeting_count} nafar."
    )
    return _module_report(
        key="otaliq",
        title="Otaliqdagi yoshlar",
        total_label="Jami otaliqdagi yoshlar",
        total_value=total_youth,
        covered_label="Yordam ko'rsatilgan",
        covered_value=assisted_count,
        covered_percent=percent,
        secondary_metrics=[
            {"label": "Uchrashuv o'tkazilgan", "value": with_meeting_count},
            {"label": "Biriktirilgan rahbarlar", "value": leader_total},
        ],
        breakdowns=[
            {"title": "Yordam yo'nalishlari", "items": assistance_breakdown},
            {"title": "Rahbarlar darajasi", "items": leader_breakdown},
            {"title": "Otaliq toifalari", "items": category_breakdown},
        ],
        summary=summary,
    )


def _collect_migratsiya_module(period: ReportPeriod, mode: str) -> dict:
    if mode == "DATE_RANGE":
        base_qs = MigrationYouth.objects.all()
    else:
        base_qs = _apply_scope(MigrationYouth.objects.all(), "created_at__date", mode, period)

    if mode == "LIVE_SVOD":
        meeting_qs = MigrationMeeting.objects.filter(migration_youth__in=base_qs)
    elif mode == "DATE_RANGE":
        meeting_qs = MigrationMeeting.objects.filter(
            migration_youth__in=base_qs,
            meeting_date__date__range=(period.start_date, period.end_date),
        )
    else:
        meeting_qs = MigrationMeeting.objects.filter(
            migration_youth__in=base_qs,
            meeting_date__date__lte=period.end_date,
        )

    total_youth = base_qs.count()
    with_meeting_count = meeting_qs.values("migration_youth_id").distinct().count()
    meeting_count = meeting_qs.count()
    percent = round((with_meeting_count / total_youth) * 100, 1) if total_youth else 0.0

    reason_rows = base_qs.values("reason").annotate(count=Count("id")).order_by("-count")
    reason_map = {row["reason"]: row["count"] for row in reason_rows}
    reason_breakdown, _ = _build_labeled_breakdown(
        reason_map,
        list(MigrationYouth.REASON_CHOICES),
        unknown_label_prefix="Boshqa sabab",
        include_unspecified=True,
    )

    country_rows = (
        base_qs.values("destination_country")
        .annotate(count=Count("id"))
        .order_by("-count", "destination_country")
    )
    country_breakdown = _build_text_breakdown(country_rows, "destination_country", limit=10)

    return_plan_count = meeting_qs.filter(return_date__isnull=False).count()
    avg_income = meeting_qs.aggregate(avg_income=Avg("work_income"))["avg_income"]

    summary = (
        f"Jami {total_youth} nafar migratsiyadagi yoshdan {with_meeting_count} nafari bilan "
        f"suhbat o'tkazilgan ({percent}%). Suhbatlar soni {meeting_count} ta."
    )

    return _module_report(
        key="migratsiya",
        title="Migratsiya bo'limi",
        total_label="Jami migratsiyadagi yoshlar",
        total_value=total_youth,
        covered_label="Suhbat o'tkazilgan yoshlar",
        covered_value=with_meeting_count,
        covered_percent=percent,
        secondary_metrics=[
            {"label": "Suhbatlar soni", "value": meeting_count},
            {"label": "Qaytish sanasi belgilangan", "value": return_plan_count},
            {"label": "O'rtacha oylik daromad", "value": _as_number_display(avg_income)},
        ],
        breakdowns=[
            {"title": "Chiqib ketish sabablari", "items": reason_breakdown},
            {"title": "Davlatlar kesimi (Top-10)", "items": country_breakdown},
        ],
        summary=summary,
    )


def _collect_kredit_module(period: ReportPeriod, mode: str) -> dict:
    if mode == "DATE_RANGE":
        base_qs = CreditCandidate.objects.all()
    else:
        base_qs = _apply_scope(CreditCandidate.objects.all(), "created_at__date", mode, period)

    total_candidates = base_qs.count()
    approved_count = base_qs.filter(stage="APPROVED").count()
    approved_percent = round((approved_count / total_candidates) * 100, 1) if total_candidates else 0.0

    stage_rows = base_qs.values("stage").annotate(count=Count("id")).order_by("-count")
    stage_map = {row["stage"]: row["count"] for row in stage_rows}
    stage_breakdown, _ = _build_labeled_breakdown(
        stage_map,
        list(CreditCandidate.STAGE_CHOICES),
        unknown_label_prefix="Boshqa bosqich",
    )

    basis_rows = base_qs.values("decision_basis").annotate(count=Count("id")).order_by("-count")
    basis_map = {row["decision_basis"]: row["count"] for row in basis_rows}
    basis_breakdown, _ = _build_labeled_breakdown(
        basis_map,
        list(CreditCandidate.DECISION_BASIS_CHOICES),
        unknown_label_prefix="Boshqa asos",
        include_unspecified=True,
    )

    business_rows = base_qs.values("business_type").annotate(count=Count("id")).order_by("-count")
    business_map = {row["business_type"]: row["count"] for row in business_rows}
    business_breakdown, _ = _build_labeled_breakdown(
        business_map,
        list(CreditCandidate.BUSINESS_TYPE_CHOICES),
        unknown_label_prefix="Boshqa yo'nalish",
        include_unspecified=True,
    )

    totals = base_qs.aggregate(
        requested=Sum("requested_amount"),
        granted=Sum("credit_amount"),
    )
    in_process_count = base_qs.filter(stage="IN_PROCESS").count()
    rejected_count = base_qs.filter(stage="REJECTED").count()

    summary = (
        f"Jami {total_candidates} nafar kredit nomzodidan {approved_count} nafariga kredit ajratilgan "
        f"({approved_percent}%)."
    )

    return _module_report(
        key="kredit_yo_naltirish",
        title="Kredit yo'naltirish",
        total_label="Jami kredit nomzodlari",
        total_value=total_candidates,
        covered_label="Kredit ajratilgan",
        covered_value=approved_count,
        covered_percent=approved_percent,
        secondary_metrics=[
            {"label": "Jarayonda", "value": in_process_count},
            {"label": "Rad etilgan", "value": rejected_count},
            {"label": "So'ralgan summa", "value": _as_number_display(totals.get("requested"))},
            {"label": "Ajratilgan summa", "value": _as_number_display(totals.get("granted"))},
        ],
        breakdowns=[
            {"title": "Bosqichlar kesimi", "items": stage_breakdown},
            {"title": "Qaror asosi", "items": basis_breakdown},
            {"title": "Biznes yo'nalishlari", "items": business_breakdown},
        ],
        summary=summary,
    )


def _collect_reyd_module(period: ReportPeriod, mode: str) -> dict:
    if mode == "LIVE_SVOD":
        event_qs = RaidEvent.objects.all()
    elif mode == "DATE_RANGE":
        event_qs = RaidEvent.objects.filter(event_date__range=(period.start_date, period.end_date))
    else:
        event_qs = RaidEvent.objects.filter(event_date__lte=period.end_date)

    total_events = event_qs.count()
    type_rows = event_qs.values("event_type").annotate(count=Count("id")).order_by("-count")
    type_map = {row["event_type"]: row["count"] for row in type_rows}
    type_breakdown, _ = _build_labeled_breakdown(
        type_map,
        list(RaidEvent.TYPE_CHOICES),
        unknown_label_prefix="Boshqa reyd turi",
    )

    photo_qs = RaidPhoto.objects.filter(event__in=event_qs)
    photo_count = photo_qs.count()
    events_with_photo = event_qs.filter(photos__isnull=False).distinct().count()
    photo_percent = round((events_with_photo / total_events) * 100, 1) if total_events else 0.0

    mahalla_rows = (
        event_qs.values("mahalla__name")
        .annotate(count=Count("id"))
        .order_by("-count", "mahalla__name")
    )
    mahalla_breakdown = _build_text_breakdown(mahalla_rows, "mahalla__name", limit=10)

    summary = (
        f"Jami {total_events} ta reyd tadbiri, shundan {events_with_photo} tasiga foto biriktirilgan "
        f"({photo_percent}%)."
    )

    return _module_report(
        key="reyd",
        title="Reyd bo'limi",
        total_label="Jami reyd tadbirlari",
        total_value=total_events,
        covered_label="Foto biriktirilgan reydlar",
        covered_value=events_with_photo,
        covered_percent=photo_percent,
        secondary_metrics=[
            {"label": "Reyd rasmlari", "value": photo_count},
        ],
        breakdowns=[
            {"title": "Reyd turlari", "items": type_breakdown},
            {"title": "Mahalla kesimi (Top-10)", "items": mahalla_breakdown},
        ],
        summary=summary,
    )


def _collect_yoqlama_module(period: ReportPeriod, mode: str) -> dict:
    if mode == "LIVE_SVOD":
        session_qs = AttendanceSession.objects.all()
    elif mode == "DATE_RANGE":
        session_qs = AttendanceSession.objects.filter(session_date__date__range=(period.start_date, period.end_date))
    else:
        session_qs = AttendanceSession.objects.filter(session_date__date__lte=period.end_date)

    total_sessions = session_qs.count()
    record_qs = AttendanceRecord.objects.filter(session__in=session_qs)
    total_records = record_qs.count()

    status_rows = record_qs.values("status").annotate(count=Count("id")).order_by("-count")
    status_map = {row["status"]: row["count"] for row in status_rows}
    status_breakdown, _ = _build_labeled_breakdown(
        status_map,
        list(AttendanceRecord.STATUS_CHOICES),
        unknown_label_prefix="Boshqa holat",
        include_unspecified=True,
    )

    session_rows = session_qs.values("session_type").annotate(count=Count("id")).order_by("-count")
    session_map = {row["session_type"]: row["count"] for row in session_rows}
    session_breakdown, _ = _build_labeled_breakdown(
        session_map,
        list(AttendanceSession.SESSION_TYPE_CHOICES),
        unknown_label_prefix="Boshqa yig'ilish turi",
    )

    attended_count = record_qs.filter(status__in=["ON_TIME", "LATE"]).count()
    attended_percent = round((attended_count / total_records) * 100, 1) if total_records else 0.0
    unexcused_count = record_qs.filter(status="UNEXCUSED").count()

    summary = (
        f"{total_sessions} ta yo'qlama majlisida jami {total_records} ta qatnashuv qaydi bor. "
        f"Shundan qatnashganlar {attended_count} ta ({attended_percent}%)."
    )

    return _module_report(
        key="yoqlama",
        title="Yo'qlama bo'limi",
        total_label="Yo'qlama qaydlari",
        total_value=total_records,
        covered_label="Qatnashgan qaydlar",
        covered_value=attended_count,
        covered_percent=attended_percent,
        secondary_metrics=[
            {"label": "Majlislar soni", "value": total_sessions},
            {"label": "Sababsiz qatnashmagan", "value": unexcused_count},
        ],
        breakdowns=[
            {"title": "Majlis turlari", "items": session_breakdown},
            {"title": "Qatnashuv holati", "items": status_breakdown},
        ],
        summary=summary,
    )


def _collect_beshtashabbus_module(period: ReportPeriod, mode: str) -> dict:
    if mode == "LIVE_SVOD":
        event_qs = FiveInitiativeEvent.objects.all()
    elif mode == "DATE_RANGE":
        event_qs = FiveInitiativeEvent.objects.filter(event_date__range=(period.start_date, period.end_date))
    else:
        event_qs = FiveInitiativeEvent.objects.filter(event_date__lte=period.end_date)

    total_events = event_qs.count()
    coverage_sum = _as_int(event_qs.aggregate(total=Sum("coverage"))["total"])

    event_direction_rows = event_qs.values("direction").annotate(count=Count("id")).order_by("-count")
    event_direction_map = {row["direction"]: row["count"] for row in event_direction_rows}
    event_direction_breakdown, _ = _build_labeled_breakdown(
        event_direction_map,
        list(FiveInitiativeEvent.DIRECTION_CHOICES),
        unknown_label_prefix="Boshqa yo'nalish",
    )

    snapshot_qs = _apply_scope(FiveInitiativeApplicationSnapshot.objects.all(), "created_at__date", mode, period)
    snapshot_count = snapshot_qs.count()
    latest_snapshot = snapshot_qs.order_by("-created_at").first()
    if latest_snapshot:
        entry_qs = FiveInitiativeApplicationEntry.objects.filter(snapshot=latest_snapshot)
        latest_snapshot_label = timezone.localtime(latest_snapshot.created_at).strftime("%d.%m.%Y %H:%M")
    else:
        entry_qs = FiveInitiativeApplicationEntry.objects.none()
        latest_snapshot_label = None

    total_entries = entry_qs.count()
    unique_participants = entry_qs.values("pinfl").distinct().count()

    selection_rows = (
        entry_qs.values("selection_category")
        .annotate(count=Count("id"))
        .order_by("-count", "selection_category")
    )
    selection_breakdown = _build_text_breakdown(selection_rows, "selection_category", limit=10)

    application_direction_rows = (
        entry_qs.values("direction")
        .annotate(count=Count("id"))
        .order_by("-count", "direction")
    )
    application_direction_breakdown = _build_text_breakdown(application_direction_rows, "direction", limit=10)

    summary = (
        f"{total_events} ta 5 tashabbus tadbiri o'tkazilgan, umumiy qamrov {coverage_sum}. "
        f"So'nggi snapshot arizalari: {total_entries} ta."
    )

    secondary_metrics = [
        {"label": "Umumiy qamrov", "value": coverage_sum},
        {"label": "Snapshotlar soni", "value": snapshot_count},
        {"label": "Noyob ishtirokchilar", "value": unique_participants},
    ]
    if latest_snapshot_label:
        secondary_metrics.append({"label": "So'nggi snapshot", "value": latest_snapshot_label})

    return _module_report(
        key="beshtashabbus",
        title="5 tashabbus",
        total_label="Jami tadbirlar",
        total_value=total_events,
        covered_label="So'nggi snapshot arizalari",
        covered_value=total_entries,
        covered_percent=None,
        secondary_metrics=secondary_metrics,
        breakdowns=[
            {"title": "Tadbir yo'nalishlari", "items": event_direction_breakdown},
            {"title": "Ariza kategoriyalari (Top-10)", "items": selection_breakdown},
            {"title": "Ariza yo'nalishlari (Top-10)", "items": application_direction_breakdown},
        ],
        summary=summary,
    )


def _collect_intizom_module(period: ReportPeriod, mode: str) -> dict:
    if mode == "LIVE_SVOD":
        action_qs = DisciplineAction.objects.all()
    elif mode == "DATE_RANGE":
        action_qs = DisciplineAction.objects.filter(action_date__range=(period.start_date, period.end_date))
    else:
        action_qs = DisciplineAction.objects.filter(action_date__lte=period.end_date)

    total_actions = action_qs.count()
    resolved_count = action_qs.filter(status="YECHILGAN").count()
    active_count = action_qs.filter(status="BOR").count()
    resolved_percent = round((resolved_count / total_actions) * 100, 1) if total_actions else 0.0

    action_type_rows = action_qs.values("action_type").annotate(count=Count("id")).order_by("-count")
    action_type_map = {row["action_type"]: row["count"] for row in action_type_rows}
    action_type_breakdown, _ = _build_labeled_breakdown(
        action_type_map,
        list(DisciplineAction.ACTION_CHOICES),
        unknown_label_prefix="Boshqa jazo turi",
    )

    status_rows = action_qs.values("status").annotate(count=Count("id")).order_by("-count")
    status_map = {row["status"]: row["count"] for row in status_rows}
    status_breakdown, _ = _build_labeled_breakdown(
        status_map,
        list(DisciplineAction.STATUS_CHOICES),
        unknown_label_prefix="Boshqa holat",
    )

    summary = (
        f"Jami {total_actions} ta intizomiy jazo qaydi, shundan {resolved_count} tasi yechilgan "
        f"({resolved_percent}%), {active_count} tasi joriy."
    )

    return _module_report(
        key="intizom_jazo",
        title="Intizomiy jazo",
        total_label="Jami jazo qaydlari",
        total_value=total_actions,
        covered_label="Yechilgan holatlar",
        covered_value=resolved_count,
        covered_percent=resolved_percent,
        secondary_metrics=[
            {"label": "Joriy holatdagilar", "value": active_count},
        ],
        breakdowns=[
            {"title": "Jazo turlari", "items": action_type_breakdown},
            {"title": "Holatlar kesimi", "items": status_breakdown},
        ],
        summary=summary,
    )


def _collect_bilim_module(period: ReportPeriod, mode: str) -> dict:
    config_qs = _apply_scope(TestConfig.objects.all(), "start_time__date", mode, period)
    result_qs = _apply_scope(TestResult.objects.all(), "started_at__date", mode, period)
    package_qs = _apply_scope(QuestionPackage.objects.all(), "created_at__date", mode, period)
    question_qs = _apply_scope(Question.objects.all(), "created_at__date", mode, period)

    total_configs = config_qs.count()
    total_results = result_qs.count()
    finished_count = result_qs.filter(finished_at__isnull=False).count()
    finished_percent = round((finished_count / total_results) * 100, 1) if total_results else 0.0

    averages = result_qs.aggregate(
        avg_score=Avg("score"),
        avg_correct=Avg("correct_answers_count"),
    )

    top_test_rows = (
        result_qs.values("test_config__title")
        .annotate(count=Count("id"))
        .order_by("-count", "test_config__title")
    )
    top_tests = _build_text_breakdown(top_test_rows, "test_config__title", limit=10)

    subject_rows = (
        result_qs.values("test_config__subject__name")
        .annotate(count=Count("id"))
        .order_by("-count", "test_config__subject__name")
    )
    subject_breakdown = _build_text_breakdown(subject_rows, "test_config__subject__name", limit=10)

    total_packages = package_qs.count()
    total_questions = question_qs.count()

    summary = (
        f"{total_results} ta test natijasi qayd etilgan, yakunlanganlari {finished_count} ta "
        f"({finished_percent}%). Faol konfiguratsiyalar: {total_configs} ta."
    )

    return _module_report(
        key="bilim_sinovi",
        title="Bilim sinovi",
        total_label="Test natijalari",
        total_value=total_results,
        covered_label="Yakunlangan testlar",
        covered_value=finished_count,
        covered_percent=finished_percent,
        secondary_metrics=[
            {"label": "Konfiguratsiyalar", "value": total_configs},
            {"label": "Savollar paketlari", "value": total_packages},
            {"label": "Savollar", "value": total_questions},
            {"label": "O'rtacha ball", "value": _as_number_display(averages.get("avg_score"))},
            {"label": "O'rtacha to'g'ri javob", "value": _as_number_display(averages.get("avg_correct"))},
        ],
        breakdowns=[
            {"title": "Eng ko'p topshirilgan testlar (Top-10)", "items": top_tests},
            {"title": "Fanlar kesimi (Top-10)", "items": subject_breakdown},
        ],
        summary=summary,
    )


def collect_unemployed_snapshot(period: ReportPeriod) -> dict:
    mode, as_of_date = _resolve_calculation_mode(period)
    module_reports = [
        _collect_ishsiz_module(period, mode),
        _collect_otaliq_module(period, mode),
        _collect_migratsiya_module(period, mode),
        _collect_kredit_module(period, mode),
        _collect_reyd_module(period, mode),
        _collect_yoqlama_module(period, mode),
        _collect_beshtashabbus_module(period, mode),
        _collect_intizom_module(period, mode),
        _collect_bilim_module(period, mode),
    ]

    total_entities = sum(_as_int(item.get("total_value")) for item in module_reports)
    comparable_modules = [
        item
        for item in module_reports
        if item.get("covered_value") is not None and item.get("covered_percent") is not None
    ]
    comparable_total = sum(_as_int(item.get("total_value")) for item in comparable_modules)
    covered_total = sum(_as_int(item.get("covered_value")) for item in comparable_modules)
    covered_percent = round((covered_total / comparable_total) * 100, 1) if comparable_total else 0.0

    ishsiz_report = next((item for item in module_reports if item.get("key") == "ishsiz_yoshlar"), None)
    ishsiz_flat = (ishsiz_report or {}).get("flat", {})

    return {
        "period_label": period.label,
        "period_date_range": period.date_range_label,
        "as_of_date": as_of_date.strftime("%d.%m.%Y"),
        "calculation_mode": mode,
        "calculation_mode_label": _calculation_mode_label(mode),
        "module_reports": module_reports,
        "module_count": len(module_reports),
        "aggregate_total": total_entities,
        "aggregate_covered": covered_total,
        "aggregate_covered_percent": covered_percent,
        "aggregate_coverage_base": comparable_total,
        # backward compatibility with existing single-module UI/testing keys:
        "total_youth": ishsiz_flat.get("total_youth", _as_int((ishsiz_report or {}).get("total_value"))),
        "with_meeting_count": ishsiz_flat.get("with_meeting_count", 0),
        "assisted_count": ishsiz_flat.get("assisted_count", _as_int((ishsiz_report or {}).get("covered_value"))),
        "assisted_percent": ishsiz_flat.get("assisted_percent", (ishsiz_report or {}).get("covered_percent", 0.0)),
        "not_assisted_count": ishsiz_flat.get("not_assisted_count", 0),
        "leader_total": ishsiz_flat.get("leader_total", 0),
        "leader_breakdown": ishsiz_flat.get("leader_breakdown", []),
        "assistance_breakdown": ishsiz_flat.get("assistance_breakdown", []),
        "youth_category_breakdown": ishsiz_flat.get("youth_category_breakdown", []),
    }


def _legacy_narrative(stats: dict) -> str:
    period_label = stats.get("period_label") or "Tanlangan davr"
    total_youth = _as_int(stats.get("total_youth"))
    assisted_count = _as_int(stats.get("assisted_count"))
    assisted_percent = stats.get("assisted_percent", 0)
    with_meeting_count = _as_int(stats.get("with_meeting_count"))
    not_assisted = _as_int(stats.get("not_assisted_count"))

    leader_items = stats.get("leader_breakdown") or []
    assistance_items = stats.get("assistance_breakdown") or []

    leader_text = ", ".join(f"{item.get('count', 0)} nafar {item.get('label', '')}" for item in leader_items[:3])
    assistance_text = ", ".join(
        f"{item.get('count', 0)} nafar {item.get('label', '')}".strip() for item in assistance_items[:7]
    )

    return (
        f"{period_label} holatiga ko'ra ishsiz toifaga kiritilgan {total_youth} nafar yoshlarning "
        f"{assisted_percent}% qismiga turli yordamlar ko'rsatilgan. "
        f"Uchrashuv o'tkazilganlar soni {with_meeting_count} nafar. "
        f"Yordam ko'rsatilganlar {assisted_count} nafar, ko'rsatilmaganlar {not_assisted} nafar. "
        f"Rahbarlar kesimi: {leader_text or 'ma`lumot yo`q'}. "
        f"Yordam yo'nalishlari: {assistance_text or 'ma`lumot yo`q'}."
    )


def build_default_narrative(stats: dict) -> str:
    module_reports = stats.get("module_reports") or []
    if not module_reports:
        return _legacy_narrative(stats)

    period_label = stats.get("period_label") or "Tanlangan davr"
    date_range = stats.get("period_date_range") or ""
    calculation_mode = stats.get("calculation_mode_label") or ""
    as_of_date = stats.get("as_of_date") or ""

    aggregate_total = stats.get("aggregate_total", 0)
    aggregate_covered = stats.get("aggregate_covered", 0)
    aggregate_covered_percent = stats.get("aggregate_covered_percent", 0)
    aggregate_coverage_base = stats.get("aggregate_coverage_base", aggregate_total)
    if aggregate_coverage_base == aggregate_total:
        aggregate_line = (
            f"Jami {stats.get('module_count', len(module_reports))} ta bo'lim bo'yicha "
            f"{aggregate_total} ta asosiy ko'rsatkich qaydi mavjud. "
            f"Shundan qamrab olingan ko'rsatkichlar {aggregate_covered} ta "
            f"({aggregate_covered_percent}%)."
        )
    else:
        aggregate_line = (
            f"Jami {stats.get('module_count', len(module_reports))} ta bo'lim bo'yicha "
            f"{aggregate_total} ta asosiy ko'rsatkich qaydi mavjud. "
            f"Foizli qamrov hisobida bazaviy ko'rsatkichlar {aggregate_coverage_base} ta bo'lib, "
            f"qamrab olingani {aggregate_covered} ta ({aggregate_covered_percent}%)."
        )

    lines = [
        (
            f"{period_label} holatiga ko'ra ({date_range}) tizim bo'limlari kesimidagi umumiy hisobot. "
            f"Hisoblash rejimi: {calculation_mode}. Davr yakuni sanasi: {as_of_date}."
        ),
        aggregate_line,
    ]

    for module in module_reports:
        title = module.get("title", "")
        total_label = module.get("total_label", "Jami")
        total_value = _as_int(module.get("total_value"))
        covered_label = module.get("covered_label")
        covered_value = module.get("covered_value")
        covered_percent = module.get("covered_percent")
        summary = module.get("summary") or ""

        parts = [f"{title}: {total_label} {total_value} ta"]
        if covered_label and covered_value is not None:
            if covered_percent is None:
                parts.append(f"{covered_label.lower()} {covered_value} ta")
            else:
                parts.append(f"{covered_label.lower()} {covered_value} ta ({covered_percent}%)")

        secondary = module.get("secondary_metrics") or []
        secondary_text = ", ".join(
            f"{item.get('label', '')} {item.get('value', '')}".strip()
            for item in secondary[:3]
            if item.get("label")
        )
        sentence = "; ".join(parts) + "."
        if secondary_text:
            sentence += f" Qo'shimcha: {secondary_text}."
        if summary:
            sentence += f" {summary}"
        lines.append(sentence)

    return "\n".join(lines)


def _extract_chat_content(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""

    first_choice = choices[0] or {}
    message = first_choice.get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks = []
        for part in content:
            if isinstance(part, dict):
                text_value = part.get("text")
                if isinstance(text_value, str):
                    chunks.append(text_value)
        return "\n".join(chunks).strip()

    text = first_choice.get("text")
    if isinstance(text, str):
        return text.strip()
    return ""


def polish_narrative_with_ai(report_text: str, stats: dict) -> tuple[str, bool, str | None]:
    base_url = str(getattr(settings, "REPORT_AI_BASE_URL", "") or "").strip()
    api_key = str(getattr(settings, "OPENAI_API_KEY", "") or "").strip()
    model = str(getattr(settings, "REPORT_AI_MODEL", "") or "gpt-4.1-mini").strip()

    if not base_url:
        return report_text, False, "AI manzili (REPORT_AI_BASE_URL) sozlanmagan."
    if not api_key:
        return report_text, False, "OPENAI_API_KEY sozlanmagan."

    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        endpoint = normalized
    else:
        endpoint = f"{normalized}/chat/completions"

    compact_stats = {
        "period_label": stats.get("period_label"),
        "period_date_range": stats.get("period_date_range"),
        "as_of_date": stats.get("as_of_date"),
        "module_reports": [
            {
                "title": module.get("title"),
                "total_label": module.get("total_label"),
                "total_value": module.get("total_value"),
                "covered_label": module.get("covered_label"),
                "covered_value": module.get("covered_value"),
                "covered_percent": module.get("covered_percent"),
                "secondary_metrics": module.get("secondary_metrics", []),
            }
            for module in (stats.get("module_reports") or [])
        ],
    }

    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Siz rasmiy hisobot matnini tartibga keltirasiz. "
                    "Raqamlar va foizlarni o'zgartirmang. Matnni aniq, ixcham va rasmiy uslubda qayta yozing."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Quyidagi hisobot matnini rasmiy va tushunarli shaklga keltiring.\n\n"
                    f"Matn:\n{report_text}\n\n"
                    f"Tekshiruv uchun ma'lumotlar:\n{json.dumps(compact_stats, ensure_ascii=False)}"
                ),
            },
        ],
    }

    req = Request(
        endpoint,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )

    try:
        with urlopen(req, timeout=35) as response:
            raw_body = response.read().decode("utf-8", errors="replace")
        decoded = json.loads(raw_body)
        content = _extract_chat_content(decoded)
        if not content:
            return report_text, False, "AI javobidan matn olinmadi."
        return content, True, None
    except HTTPError as exc:
        return report_text, False, f"AI xizmatida HTTP xatolik: {exc.code}"
    except URLError:
        return report_text, False, "AI xizmatiga ulanib bo'lmadi."
    except (TimeoutError, ValueError, json.JSONDecodeError):
        return report_text, False, "AI javobi noto'g'ri formatda keldi."


def _font_candidates() -> list[str]:
    candidates: list[str] = []
    custom_regular = str(getattr(settings, "REPORT_FONT_PATH", "") or "").strip()
    custom_bold = str(getattr(settings, "REPORT_FONT_BOLD_PATH", "") or "").strip()
    if custom_regular:
        candidates.append(custom_regular)
    if custom_bold and custom_bold not in candidates:
        candidates.append(custom_bold)
    return candidates


def _split_wrapped_lines(text: str, max_chars: int = 95) -> list[str]:
    lines: list[str] = []
    for raw_line in (text or "").splitlines():
        clean = raw_line.strip()
        if not clean:
            lines.append("")
            continue
        wrapped = textwrap.wrap(clean, width=max_chars)
        lines.extend(wrapped or [""])
    return lines


_CYRILLIC_TO_LATIN = {
    "А": "A",
    "а": "a",
    "Б": "B",
    "б": "b",
    "В": "V",
    "в": "v",
    "Г": "G",
    "г": "g",
    "Д": "D",
    "д": "d",
    "Е": "E",
    "е": "e",
    "Ё": "Yo",
    "ё": "yo",
    "Ж": "J",
    "ж": "j",
    "З": "Z",
    "з": "z",
    "И": "I",
    "и": "i",
    "Й": "Y",
    "й": "y",
    "К": "K",
    "к": "k",
    "Л": "L",
    "л": "l",
    "М": "M",
    "м": "m",
    "Н": "N",
    "н": "n",
    "О": "O",
    "о": "o",
    "П": "P",
    "п": "p",
    "Р": "R",
    "р": "r",
    "С": "S",
    "с": "s",
    "Т": "T",
    "т": "t",
    "У": "U",
    "у": "u",
    "Ф": "F",
    "ф": "f",
    "Х": "X",
    "х": "x",
    "Ҳ": "H",
    "ҳ": "h",
    "Ц": "Ts",
    "ц": "ts",
    "Ч": "Ch",
    "ч": "ch",
    "Ш": "Sh",
    "ш": "sh",
    "Щ": "Shch",
    "щ": "shch",
    "Ъ": "",
    "ъ": "",
    "Ы": "I",
    "ы": "i",
    "Ь": "",
    "ь": "",
    "Э": "E",
    "э": "e",
    "Ю": "Yu",
    "ю": "yu",
    "Я": "Ya",
    "я": "ya",
    "Ў": "O'",
    "ў": "o'",
    "Қ": "Q",
    "қ": "q",
    "Ғ": "G'",
    "ғ": "g'",
}


def _normalize_pdf_text(text: str) -> str:
    normalized = "".join(_CYRILLIC_TO_LATIN.get(ch, ch) for ch in (text or ""))
    normalized = normalized.replace("`", "'").replace("\t", " ")
    cleaned_chars: list[str] = []
    for ch in normalized:
        code = ord(ch)
        if ch == "\n":
            cleaned_chars.append(" ")
            continue
        if 32 <= code <= 126:
            cleaned_chars.append(ch)
        elif code > 126:
            cleaned_chars.append(" ")
    result = "".join(cleaned_chars)
    return " ".join(result.split())


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_minimal_pdf(lines: list[str]) -> bytes:
    page_height = 842
    start_x = 45
    start_y = 800
    line_height = 14
    max_lines = 50
    pages = [lines[index : index + max_lines] for index in range(0, len(lines), max_lines)] or [[]]
    page_count = len(pages)

    objects: dict[int, bytes] = {}
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    page_ids = [4 + i for i in range(page_count)]
    content_ids = [4 + page_count + i for i in range(page_count)]
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[2] = f"<< /Type /Pages /Count {page_count} /Kids [{kids}] >>".encode("ascii")
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    for idx, page_lines in enumerate(pages):
        page_id = page_ids[idx]
        content_id = content_ids[idx]
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 {page_height}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("ascii")

        commands = ["BT", "/F1 11 Tf", f"{start_x} {start_y} Td", f"{line_height} TL"]
        first_line = True
        for line in page_lines:
            safe = _pdf_escape(_normalize_pdf_text(line))
            if first_line:
                commands.append(f"({safe}) Tj")
                first_line = False
            else:
                commands.append(f"T* ({safe}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", errors="ignore")
        objects[content_id] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    max_id = max(objects)
    offsets = [0] * (max_id + 1)

    for obj_id in range(1, max_id + 1):
        offsets[obj_id] = len(output)
        output.extend(f"{obj_id} 0 obj\n".encode("ascii"))
        output.extend(objects[obj_id])
        output.extend(b"\nendobj\n")

    xref_start = len(output)
    output.extend(f"xref\n0 {max_id + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for obj_id in range(1, max_id + 1):
        output.extend(f"{offsets[obj_id]:010d} 00000 n \n".encode("ascii"))

    output.extend(
        (
            f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        ).encode("ascii")
    )
    return bytes(output)


def build_pdf_bytes(period_label: str, date_range_label: str, report_text: str, stats: dict) -> bytes:
    lines: list[str] = [
        "Hisobot",
        f"Davr: {period_label}",
        f"Sana oraligi: {date_range_label}",
        f"Davr yakuni: {stats.get('as_of_date', '-')}",
        f"Hisoblash rejimi: {stats.get('calculation_mode_label', '-')}",
        "",
        "Shakllangan hisobot matni:",
    ]
    lines.extend(_split_wrapped_lines(report_text, max_chars=96))

    module_reports = stats.get("module_reports") or []
    if module_reports:
        lines.append("")
        lines.append("Modullar kesimida:")
        for module in module_reports:
            lines.append(f"{module.get('title', 'Modul')}:")
            lines.extend(
                _split_wrapped_lines(
                    f"- {module.get('total_label', 'Jami')}: {module.get('total_value', 0)}",
                    max_chars=96,
                )
            )
            if module.get("covered_label") and module.get("covered_value") is not None:
                covered_line = f"- {module['covered_label']}: {module['covered_value']}"
                if module.get("covered_percent") is not None:
                    covered_line += f" ({module['covered_percent']}%)"
                lines.extend(_split_wrapped_lines(covered_line, max_chars=96))
            for metric in (module.get("secondary_metrics") or [])[:4]:
                lines.extend(_split_wrapped_lines(f"- {metric.get('label')}: {metric.get('value')}", max_chars=96))
            for breakdown in (module.get("breakdowns") or [])[:2]:
                lines.extend(_split_wrapped_lines(f"- {breakdown.get('title')}", max_chars=96))
                for item in (breakdown.get("items") or [])[:6]:
                    lines.extend(
                        _split_wrapped_lines(
                            f"  * {item.get('label')}: {item.get('count')}",
                            max_chars=96,
                        )
                    )
            lines.append("")
    else:
        lines.extend(
            [
                "",
                f"Jami ishsiz yoshlar: {stats.get('total_youth', 0)}",
                f"Yordam ko'rsatilgan: {stats.get('assisted_count', 0)} ({stats.get('assisted_percent', 0)}%)",
                f"Yordam ko'rsatilmagan: {stats.get('not_assisted_count', 0)}",
            ]
        )

    return _build_minimal_pdf(lines)


def available_assistance_types() -> list[dict]:
    items = []
    for code, label in AssistanceInfo.ASSISTANCE_TYPES:
        items.append({"module": "ishsiz_yoshlar", "code": code, "label": label})
    for code, label in OtaliqAssistance.ASSISTANCE_TYPES:
        items.append({"module": "otaliq", "code": code, "label": label})
    return items
