from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import KpiColumnPref, Mahalla
from core.services.kpi_service import MODULE_COLUMNS, build_module_rows, traffic_color


class KpiColumnPrefModelTest(TestCase):
    def test_unique_user_column(self):
        user = get_user_model().objects.create_user(
            username="colpref", full_name="Pref User", role="YETAKCHI"
        )
        KpiColumnPref.objects.create(user=user, column_key="otaliq", visible=True)
        with self.assertRaises(Exception):
            KpiColumnPref.objects.create(user=user, column_key="otaliq", visible=False)


class BuildModuleRowsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mahalla = Mahalla.objects.create(name="Test Mahalla")
        cls.leader = get_user_model().objects.create_user(
            username="leader1", full_name="Test Yetakchi", role="YETAKCHI",
            mahalla=cls.mahalla,
        )

    def test_module_columns_has_ten(self):
        self.assertEqual(len(MODULE_COLUMNS), 10)
        keys = [c["key"] for c in MODULE_COLUMNS]
        self.assertEqual(keys[0], "otaliq")
        self.assertEqual(keys[-1], "bilim")

    def test_empty_leaders_returns_empty(self):
        self.assertEqual(build_module_rows([]), [])

    def test_missing_modules_count_zero(self):
        rows = build_module_rows([self.leader], from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["total_score"], 0.0)
        self.assertEqual(row["traffic"], "red")

    def test_traffic_color_bounds(self):
        self.assertEqual(traffic_color(85).startswith("rgba("), True)
        self.assertEqual(traffic_color(100), traffic_color(95))  # saturated green
        self.assertEqual(traffic_color(0), traffic_color(10))    # saturated red
