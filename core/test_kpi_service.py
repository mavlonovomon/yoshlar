from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import KpiColumnPref


class KpiColumnPrefModelTest(TestCase):
    def test_unique_user_column(self):
        user = get_user_model().objects.create_user(
            username="colpref", full_name="Pref User", role="YETAKCHI"
        )
        KpiColumnPref.objects.create(user=user, column_key="otaliq", visible=True)
        with self.assertRaises(Exception):
            KpiColumnPref.objects.create(user=user, column_key="otaliq", visible=False)
