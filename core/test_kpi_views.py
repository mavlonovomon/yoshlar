import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Mahalla, KpiColumnPref


class KpiViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mahalla = Mahalla.objects.create(name="View Mahalla")
        cls.user = get_user_model().objects.create_user(
            username="viewer", full_name="View User", role="SUPER_ADMIN", is_superuser=True,
        )
        cls.leader = get_user_model().objects.create_user(
            username="vleader", full_name="View Leader", role="YETAKCHI", mahalla=cls.mahalla,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_dashboard_200(self):
        resp = self.client.get(reverse("kpi_dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "KPI")

    def test_dashboard_renders_module_columns(self):
        resp = self.client.get(reverse("kpi_dashboard"))
        self.assertContains(resp, "Otaliq")
        self.assertContains(resp, "Bilim sinovi")
        self.assertContains(resp, "Itog")

    def test_dashboard_rows_have_traffic_color(self):
        resp = self.client.get(reverse("kpi_dashboard"))
        self.assertContains(resp, "rgba(")

    def test_column_toggle_creates_pref(self):
        resp = self.client.post(
            reverse("kpi_column_toggle"),
            data=json.dumps({"column_key": "otaliq", "visible": False}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        pref = KpiColumnPref.objects.get(user=self.user, column_key="otaliq")
        self.assertFalse(pref.visible)

    def test_pdf_download(self):
        resp = self.client.get(reverse("kpi_pdf"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertGreater(len(resp.content), 500)

    def test_excel_download(self):
        resp = self.client.get(reverse("kpi_excel"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml", resp["Content-Type"])
