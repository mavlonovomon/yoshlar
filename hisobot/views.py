from __future__ import annotations

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Min
from django.http import HttpResponse
from django.utils import timezone
from django.views.generic import TemplateView

from ishsiz_yoshlar.models import UnemployedYouth

from .services import (
    available_assistance_types,
    build_default_narrative,
    build_pdf_bytes,
    collect_unemployed_snapshot,
    polish_narrative_with_ai,
    resolve_report_period,
)


def _as_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_date(value, default: date) -> date:
    raw = str(value or "").strip()
    if not raw:
        return default
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return default


def _as_year_month(value, default_year: int, default_month: int) -> tuple[int, int]:
    raw = str(value or "").strip()
    if not raw:
        return default_year, default_month
    try:
        year_part, month_part = raw.split("-", 1)
        year_value = int(year_part)
        month_value = int(month_part)
        if month_value < 1 or month_value > 12:
            raise ValueError
        return year_value, month_value
    except (TypeError, ValueError):
        return default_year, default_month


class HisobotView(LoginRequiredMixin, TemplateView):
    template_name = "hisobot/index.html"

    def _default_year(self) -> int:
        first_created = UnemployedYouth.objects.aggregate(min_created=Min("created_at"))["min_created"]
        if first_created:
            return first_created.year
        return timezone.localdate().year

    def _build_form_context(self, data) -> dict:
        current_year = timezone.localdate().year
        today = timezone.localdate()
        week_start_default = today - timedelta(days=today.weekday())
        default_start = today.replace(day=1)
        default_year = self._default_year()
        selected_type = (data.get("report_type") or "QUARTER").strip().upper()
        selected_year = _as_int(data.get("year"), current_year)
        selected_quarter = _as_int(data.get("quarter"), 1)
        selected_half = _as_int(data.get("half"), 1)
        selected_day_obj = _as_date(data.get("day_date"), today)
        selected_week_start_obj = _as_date(data.get("week_start_date"), week_start_default)
        selected_month_year, selected_month = _as_year_month(data.get("month_value"), current_year, today.month)
        selected_start_obj = _as_date(data.get("start_date"), default_start)
        selected_end_obj = _as_date(data.get("end_date"), today)
        use_ai = str(data.get("use_ai", "")).strip().lower() in {"1", "on", "true", "yes"}

        years = list(range(default_year, current_year + 1))
        if not years:
            years = [current_year]

        return {
            "report_types": [
                {"value": "QUARTER", "label": "Kvartal"},
                {"value": "HALF_YEAR", "label": "Yarim yillik"},
                {"value": "YEAR", "label": "Yillik"},
                {"value": "MONTH", "label": "Oylik"},
                {"value": "WEEK", "label": "Haftalik"},
                {"value": "DAY", "label": "Kunlik"},
                {"value": "DATE_RANGE", "label": "Vaqt oralig'i"},
            ],
            "selected_type": selected_type,
            "selected_year": selected_year,
            "selected_quarter": selected_quarter if selected_quarter in {1, 2, 3, 4} else 1,
            "selected_half": selected_half if selected_half in {1, 2} else 1,
            "selected_month_value": f"{selected_month_year:04d}-{selected_month:02d}",
            "selected_month_year": selected_month_year,
            "selected_month": selected_month,
            "selected_day_date": selected_day_obj.isoformat(),
            "selected_day_date_obj": selected_day_obj,
            "selected_week_start_date": selected_week_start_obj.isoformat(),
            "selected_week_start_date_obj": selected_week_start_obj,
            "selected_start_date": selected_start_obj.isoformat(),
            "selected_end_date": selected_end_obj.isoformat(),
            "selected_start_date_obj": selected_start_obj,
            "selected_end_date_obj": selected_end_obj,
            "quarter_options": [1, 2, 3, 4],
            "half_options": [1, 2],
            "year_options": years,
            "use_ai": use_ai,
            "known_assistance_types": available_assistance_types(),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._build_form_context(self.request.GET))
        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data()
        context.update(self._build_form_context(request.POST))

        period = resolve_report_period(
            report_type=context["selected_type"],
            year=context["selected_month_year"] if context["selected_type"] == "MONTH" else context["selected_year"],
            quarter=context["selected_quarter"],
            half=context["selected_half"],
            month=context["selected_month"],
            day_date=context["selected_day_date_obj"],
            week_start=context["selected_week_start_date_obj"],
            start_date=context["selected_start_date_obj"],
            end_date=context["selected_end_date_obj"],
        )
        stats = collect_unemployed_snapshot(period)
        report_text = build_default_narrative(stats)
        ai_used = False
        ai_error = None
        if context["use_ai"]:
            report_text, ai_used, ai_error = polish_narrative_with_ai(report_text, stats)
            if ai_error:
                messages.warning(request, ai_error)

        action = (request.POST.get("action") or "preview").strip().lower()
        if action == "pdf":
            pdf_bytes = build_pdf_bytes(period.label, period.date_range_label, report_text, stats)
            if period.year:
                filename = f"hisobot_{period.report_type.lower()}_{period.year}.pdf"
            else:
                filename = f"hisobot_{period.report_type.lower()}.pdf"
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        context.update(
            {
                "period": period,
                "stats": stats,
                "report_text": report_text,
                "ai_used": ai_used,
                "ai_error": ai_error,
            }
        )
        return self.render_to_response(context)
