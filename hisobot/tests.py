from datetime import date

from django.test import SimpleTestCase

from .services import build_default_narrative, build_pdf_bytes, resolve_report_period
from .views import _as_date


class ReportPeriodTests(SimpleTestCase):
    def test_resolve_quarter_period(self):
        period = resolve_report_period("QUARTER", year=2026, quarter=2)
        self.assertEqual(period.start_date.isoformat(), "2026-04-01")
        self.assertEqual(period.end_date.isoformat(), "2026-06-30")

    def test_resolve_half_year_period(self):
        period = resolve_report_period("HALF_YEAR", year=2026, half=2)
        self.assertEqual(period.start_date.isoformat(), "2026-07-01")
        self.assertEqual(period.end_date.isoformat(), "2026-12-31")

    def test_resolve_custom_date_range_period(self):
        period = resolve_report_period(
            "DATE_RANGE",
            start_date=date(2026, 2, 10),
            end_date=date(2026, 3, 15),
        )
        self.assertEqual(period.report_type, "DATE_RANGE")
        self.assertEqual(period.start_date.isoformat(), "2026-02-10")
        self.assertEqual(period.end_date.isoformat(), "2026-03-15")

    def test_resolve_month_period(self):
        period = resolve_report_period("MONTH", year=2026, month=2)
        self.assertEqual(period.start_date.isoformat(), "2026-02-01")
        self.assertEqual(period.end_date.isoformat(), "2026-02-28")

    def test_resolve_week_period(self):
        period = resolve_report_period("WEEK", week_start=date(2026, 3, 9))
        self.assertEqual(period.start_date.isoformat(), "2026-03-09")
        self.assertEqual(period.end_date.isoformat(), "2026-03-15")

    def test_resolve_day_period(self):
        period = resolve_report_period("DAY", day_date=date(2026, 3, 11))
        self.assertEqual(period.start_date.isoformat(), "2026-03-11")
        self.assertEqual(period.end_date.isoformat(), "2026-03-11")


class ReportOutputTests(SimpleTestCase):
    def test_default_narrative_contains_key_numbers(self):
        text = build_default_narrative(
            {
                "period_label": "2026-yil 1-kvartal",
                "total_youth": 735,
                "with_meeting_count": 700,
                "assisted_percent": 99.9,
                "assisted_count": 734,
                "not_assisted_count": 1,
                "leader_total": 43,
                "leader_breakdown": [
                    {"code": "VILOYAT", "label": "Viloyat darajasi", "count": 5},
                    {"code": "TUMAN", "label": "Tuman darajasi", "count": 38},
                ],
                "assistance_breakdown": [
                    {"code": "KREDIT", "label": "Kredit", "count": 57},
                    {"code": "YER", "label": "Yer", "count": 1},
                    {"code": "SUBSIDIYA", "label": "Asbob-uskuna", "count": 13},
                    {"code": "MIGRATSIYA", "label": "Migratsiya", "count": 151},
                    {"code": "ISH", "label": "Doimiy ish", "count": 291},
                ],
                "youth_category_breakdown": [
                    {"code": "QOLGAN", "label": "Qolgan ishsizlar", "count": 735},
                ],
            }
        )
        self.assertIn("735", text)
        self.assertIn("99.9", text)
        self.assertIn("734", text)

    def test_pdf_builder_returns_pdf_bytes(self):
        stats = {
            "as_of_date": "31.03.2026",
            "total_youth": 100,
            "with_meeting_count": 80,
            "assisted_count": 75,
            "assisted_percent": 75.0,
            "not_assisted_count": 25,
            "assistance_breakdown": [
                {"code": "ISH", "label": "Doimiy ishga joylashgan", "count": 10},
                {"code": "KREDIT", "label": "Kredit", "count": 11},
            ],
            "leader_breakdown": [
                {"code": "TUMAN", "label": "Tuman darajasi", "count": 4},
            ],
        }
        payload = build_pdf_bytes(
            period_label="2026-yil 1-kvartal",
            date_range_label="01.01.2026 - 31.03.2026",
            report_text="Test hisobot matni",
            stats=stats,
        )
        self.assertTrue(payload.startswith(b"%PDF"))


class ReportViewHelpersTests(SimpleTestCase):
    def test_as_date_returns_parsed_date(self):
        parsed = _as_date("2026-03-11", date(2026, 1, 1))
        self.assertEqual(parsed, date(2026, 3, 11))

    def test_as_date_falls_back_on_invalid(self):
        fallback = date(2026, 1, 1)
        parsed = _as_date("invalid-date", fallback)
        self.assertEqual(parsed, fallback)
