from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from .models import User
from .services.kpi_service import build_kpi_rows


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


@login_required
def kpi_dashboard(request):
    period = (request.GET.get("period") or "month").strip().lower()
    if period not in {"month", "quarter", "year", "all"}:
        period = "month"

    sector = (request.GET.get("sector") or "").strip()
    query = (request.GET.get("q") or "").strip()

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
    rows = build_kpi_rows(leaders, from_date=from_date, to_date=to_date)

    top_row = rows[0] if rows else None
    avg_total = round(sum(row["total_score"] for row in rows) / len(rows), 1) if rows else 0
    high_result_count = sum(1 for row in rows if row["total_score"] >= 80)

    direction_avg = {
        "coverage": round(sum((row["coverage_score"] or 0) for row in rows) / len(rows), 2) if rows else 0,
        "employment": round(sum((row["employment_score"] or 0) for row in rows) / len(rows), 2) if rows else 0,
        "risk": round(sum((row["risk_score"] or 0) for row in rows) / len(rows), 2) if rows else 0,
        "execution": round(sum((row["execution_score"] or 0) for row in rows) / len(rows), 2) if rows else 0,
        "initiative": round(sum((row["initiative_score"] or 0) for row in rows) / len(rows), 2) if rows else 0,
    }
    best_direction_key = max(direction_avg, key=direction_avg.get) if rows else "coverage"
    direction_labels = {
        "coverage": "Qamrov",
        "employment": "Bandlik",
        "risk": "Xavf guruhlari",
        "execution": "Ijro-intizom",
        "initiative": "Tadbirlar",
    }

    period_range = (
        f"{start_dt.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')}"
        if start_dt
        else "Barcha vaqt bo'yicha"
    )

    context = {
        "rows": rows,
        "top_row": top_row,
        "avg_total": avg_total,
        "high_result_count": high_result_count,
        "leaders_count": len(rows),
        "direction_avg": direction_avg,
        "best_direction": direction_labels[best_direction_key],
        "best_direction_score": direction_avg.get(best_direction_key, 0),
        "selected_period": period,
        "selected_sector": sector,
        "q": query,
        "period_label": _period_label(period),
        "period_range": period_range,
    }
    return render(request, "kpi/dashboard.html", context)
