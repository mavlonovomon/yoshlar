import json
from datetime import date, datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import KpiColumnPref, User
from .services.kpi_service import build_module_rows, MODULE_COLUMNS, MODULE_GROUPS, traffic_color
from .kpi_exports import build_excel, build_pdf


def _period_start(period):
    now = timezone.localtime()
    if period == "all":
        return None
    if period == "year":
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    if period == "quarter":
        quarter_start_month = ((now.month - 1) // 3) * 3 + 1
        return now.replace(month=quarter_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _period_label(period):
    if period == "all":
        return "Barcha davr"
    if period == "year":
        return "Joriy yil"
    if period == "quarter":
        return "Joriy chorak"
    return "Joriy oy"


def _prev_period_bounds(period):
    """Avvalgi davr chegaralarini qaytaradi (from, to) date yoki (None, None)."""
    now = timezone.localtime().date()
    if period == "all":
        return None, None
    if period == "year":
        prev_year = now.year - 1
        return date(prev_year, 1, 1), date(prev_year, 12, 31)
    if period == "quarter":
        current_q_start = _period_start(period).date()
        prev_q_end = current_q_start - timezone.timedelta(days=1)
        prev_q_start_month = ((prev_q_end.month - 1) // 3) * 3 + 1
        return date(prev_q_end.year, prev_q_start_month, 1), prev_q_end
    # month
    current_month_start = _period_start(period).date()
    prev_end = current_month_start - timezone.timedelta(days=1)
    return date(prev_end.year, prev_end.month, 1), prev_end


@login_required
def kpi_dashboard(request):
    period = (request.GET.get("period") or "month").strip().lower()
    if period not in {"month", "quarter", "year", "all"}:
        period = "month"

    sector = (request.GET.get("sector") or "").strip()
    query = (request.GET.get("q") or "").strip()
    sort_key = (request.GET.get("sort") or "").strip()

    start_dt = _period_start(period)
    today = timezone.localdate()
    from_date = start_dt.date() if start_dt else None
    to_date = today if start_dt else None

    leaders_qs = (
        User.objects.filter(is_active=True, role="YETAKCHI")
        .select_related("mahalla")
        .order_by("full_name", "username")
    )
    if sector in {"1", "2", "3", "4"}:
        leaders_qs = leaders_qs.filter(sector=int(sector))
    if query:
        leaders_qs = leaders_qs.filter(
            Q(full_name__icontains=query)
            | Q(username__icontains=query)
            | Q(mahalla__name__icontains=query)
        )

    leaders = list(leaders_qs)
    rows = build_module_rows(leaders, from_date=from_date, to_date=to_date)

    # trend: oldingi davr bilan solishtirish
    prev_from, prev_to = _prev_period_bounds(period)
    prev_scores = {}
    if prev_from and prev_to:
        for r in build_module_rows(leaders, from_date=prev_from, to_date=prev_to):
            prev_scores[r["leader"].id] = r["total_score"]
    for r in rows:
        r["traffic_color"] = traffic_color(r["total_score"])
        prev = prev_scores.get(r["leader"].id)
        if prev is None:
            r["trend"] = None
        else:
            r["trend"] = round(r["total_score"] - prev, 2)

    # ustun sozlamalari
    prefs = {
        p.column_key: p.visible
        for p in KpiColumnPref.objects.filter(user=request.user)
    }
    module_columns = [
        {**c, "visible": prefs.get(c["key"], True)}
        for c in MODULE_COLUMNS
    ]
    visible_keys = [c["key"] for c in module_columns if c["visible"]]

    # sortirovka
    if sort_key in {c["key"] for c in MODULE_COLUMNS}:
        rows.sort(key=lambda r: r["modules"][sort_key]["pct"], reverse=True)
    for i, r in enumerate(rows, start=1):
        r["rank"] = i

    top_row = rows[0] if rows else None
    avg_total = round(sum(r["total_score"] for r in rows) / len(rows), 1) if rows else 0
    high_result_count = sum(1 for r in rows if r["total_score"] >= 80)

    direction_avg = {c["key"]: round(
        sum((r["modules"].get(c["key"], {}).get("pct") or 0) for r in rows) / len(rows), 1
    ) if rows else 0 for c in MODULE_COLUMNS}
    best_direction_key = max(direction_avg, key=direction_avg.get) if rows else MODULE_COLUMNS[0]["key"]
    best_label = next((c["label"] for c in MODULE_COLUMNS if c["key"] == best_direction_key), "-")

    period_range = (
        f"{start_dt.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')}"
        if start_dt
        else "Barcha vaqt bo'yicha"
    )

    context = {
        "rows": rows,
        "module_columns": module_columns,
        "module_groups": MODULE_GROUPS,
        "visible_keys": visible_keys,
        "column_prefs": prefs,
        "top_row": top_row,
        "avg_total": avg_total,
        "high_result_count": high_result_count,
        "leaders_count": len(rows),
        "direction_avg": direction_avg,
        "best_direction": best_label,
        "best_direction_score": direction_avg.get(best_direction_key, 0),
        "selected_period": period,
        "selected_sector": sector,
        "sort_key": sort_key,
        "q": query,
        "period_label": _period_label(period),
        "period_range": period_range,
    }
    return render(request, "kpi/dashboard.html", context)


@login_required
@require_POST
def kpi_column_toggle(request):
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "JSON noto'g'ri"}, status=400)
    column_key = str(data.get("column_key") or "")
    valid_keys = {c["key"] for c in MODULE_COLUMNS}
    if column_key not in valid_keys:
        return JsonResponse({"success": False, "error": "Noma'lum ustun"}, status=400)
    visible = bool(data.get("visible"))
    KpiColumnPref.objects.update_or_create(
        user=request.user,
        column_key=column_key,
        defaults={"visible": visible},
    )
    return JsonResponse({"success": True, "column_key": column_key, "visible": visible})


def _export_context(request, period, sector, query):
    start_dt = _period_start(period)
    today = timezone.localdate()
    from_date = start_dt.date() if start_dt else None
    to_date = today if start_dt else None
    leaders_qs = User.objects.filter(is_active=True, role="YETAKCHI").select_related("mahalla")
    if sector in {"1", "2", "3", "4"}:
        leaders_qs = leaders_qs.filter(sector=int(sector))
    if query:
        leaders_qs = leaders_qs.filter(
            Q(full_name__icontains=query)
            | Q(username__icontains=query)
            | Q(mahalla__name__icontains=query)
        )
    rows = build_module_rows(list(leaders_qs), from_date=from_date, to_date=to_date)
    for r in rows:
        r['traffic'] = traffic_color(r['total_score'])
    for i, r in enumerate(rows, start=1):
        r['rank'] = i
    prefs = {p.column_key: p.visible for p in KpiColumnPref.objects.filter(user=request.user)}
    visible_keys = [c["key"] for c in MODULE_COLUMNS if prefs.get(c["key"], True)]
    title = f"KPI reytingi - {_period_label(period)}"
    subtitle = f"{_period_label(period)} | {from_date} - {to_date}" if from_date else "Barcha davr"
    return rows, visible_keys, title, subtitle


@login_required
def kpi_pdf(request):
    period = (request.GET.get("period") or "month").strip().lower()
    if period not in {"month", "quarter", "year", "all"}:
        period = "month"
    sector = (request.GET.get("sector") or "").strip()
    query = (request.GET.get("q") or "").strip()
    rows, visible_keys, title, subtitle = _export_context(request, period, sector, query)
    pdf_bytes = build_pdf(rows, visible_keys, title, subtitle)
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="kpi_{period}_{datetime.now():%Y%m%d}.pdf"'
    return resp


@login_required
def kpi_excel(request):
    period = (request.GET.get("period") or "month").strip().lower()
    if period not in {"month", "quarter", "year", "all"}:
        period = "month"
    sector = (request.GET.get("sector") or "").strip()
    query = (request.GET.get("q") or "").strip()
    rows, visible_keys, title, subtitle = _export_context(request, period, sector, query)
    xlsx_bytes = build_excel(rows, visible_keys, title)
    resp = HttpResponse(
        xlsx_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="kpi_{period}_{datetime.now():%Y%m%d}.xlsx"'
    return resp
