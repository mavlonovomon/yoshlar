from datetime import date
from django.test import TestCase, Client
from django.urls import reverse

from core.models import (
    Mahalla,
    User,
    IbratFarzandlariStatSnapshot,
    IbratFarzandlariMahallaStat,
    IbratFarzandlariMahallaAlias,
)
from core.ibrat import _normalize_name, build_table, save_ibrat_snapshot


class IbratFarzandlariTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin_test",
            password="password123",
            role="SUPER_ADMIN",
        )
        self.mahalla = Mahalla.objects.create(name="Yangiobod")
        self.client = Client(SERVER_NAME="127.0.0.1")
        self.client.force_login(self.user)

    def test_normalize_name(self):
        self.assertEqual(_normalize_name("Yangiobod mahallasi"), "yangiobod")
        self.assertEqual(_normalize_name("G‘.G‘ulom MFY"), "ggulom")
        self.assertEqual(_normalize_name("Sulaymon qalʻʻasi"), "sulaymonqalasi")

    def test_build_table_empty(self):
        cols, rows, total = build_table(None)
        self.assertEqual(cols, [])
        self.assertEqual(rows, [])
        self.assertIsNone(total)

    def test_save_snapshot_and_build_table(self):
        payload = {
            "data": [
                {
                    "id": 8504,
                    "code": "22100045",
                    "name": "Yangiobod",
                    "user_count": 200,
                    "certificate_count": 100,
                }
            ],
            "total_count": 1,
            "last_updated_at": "2026-10-13T10:00:00Z",
        }
        snapshot = save_ibrat_snapshot(payload, source_url="https://api.ibrat.dev/test")
        self.assertEqual(snapshot.area_stats.count(), 1)

        stat = snapshot.area_stats.first()
        self.assertEqual(stat.area_name, "Yangiobod")
        self.assertEqual(stat.metrics["user_count"], 200)

        cols, rows, total = build_table(
            snapshot,
            mahallas=[self.mahalla],
            youth_counts={self.mahalla.id: 1000},
        )
        self.assertIn("users_total", cols)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["mahalla_name"], "Yangiobod")
        self.assertEqual(rows[0]["users_total"], 200)
        self.assertEqual(rows[0]["certificates_count"], 100)
        self.assertEqual(rows[0]["users_ratio_percent"], "20.0%")
        self.assertEqual(total["users_total"], 200)
        self.assertEqual(total["certificates_count"], 100)

    def test_mega_ibrat_view(self):
        url = reverse("mega_ibrat")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ibrat Farzandlari")
        self.assertIn("bajarilish xaritasi", response.content.decode("utf-8"))
