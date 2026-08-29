from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import Mahalla, Yosh
from core.views_yosh import _build_age_gender_distribution


class BuildAgeGenderDistributionTest(TestCase):
    _counter = 0

    @classmethod
    def setUpTestData(cls):
        cls.mahalla = Mahalla.objects.create(name="Test Mahalla")

    def _make_yosh(self, age, gender, name="Test"):
        BuildAgeGenderDistributionTest._counter += 1
        today = timezone.localdate()
        birth = today.replace(year=today.year - age)
        return Yosh.objects.create(
            fullname=f"{name} {age}",
            birth_date=birth,
            jshshir=f"3{BuildAgeGenderDistributionTest._counter:013d}",
            address="Test addr",
            mahalla=self.mahalla,
            school_gender=gender,
        )

    def test_returns_17_items_for_ages_14_to_30(self):
        result = _build_age_gender_distribution()
        self.assertEqual(len(result), 17)
        ages = [r["age"] for r in result]
        self.assertEqual(ages, list(range(14, 31)))

    def test_all_zeros_when_no_data(self):
        result = _build_age_gender_distribution()
        for row in result:
            self.assertEqual(row["erkaklar"], 0)
            self.assertEqual(row["ayollar"], 0)

    def test_male_counted_correctly(self):
        self._make_yosh(15, "Мужской", name="Male")
        result = _build_age_gender_distribution()
        age_row = next(r for r in result if r["age"] == 15)
        self.assertEqual(age_row["erkaklar"], 1)
        self.assertEqual(age_row["ayollar"], 0)

    def test_female_counted_correctly(self):
        self._make_yosh(20, "Женский", name="Female")
        result = _build_age_gender_distribution()
        age_row = next(r for r in result if r["age"] == 20)
        self.assertEqual(age_row["erkaklar"], 0)
        self.assertEqual(age_row["ayollar"], 1)

    def test_both_genders_in_same_age(self):
        self._make_yosh(25, "Мужской", name="Male")
        self._make_yosh(25, "Женский", name="Female")
        result = _build_age_gender_distribution()
        age_row = next(r for r in result if r["age"] == 25)
        self.assertEqual(age_row["erkaklar"], 1)
        self.assertEqual(age_row["ayollar"], 1)

    def test_base_qs_filters_results(self):
        self._make_yosh(16, "Мужской", name="A")
        qs = Yosh.objects.filter(school_gender="Мужской")
        result = _build_age_gender_distribution(base_qs=qs)
        age_row = next(r for r in result if r["age"] == 16)
        self.assertEqual(age_row["erkaklar"], 1)
        # Other ages should be zero
        other_ages = [r for r in result if r["age"] != 16]
        for r in other_ages:
            self.assertEqual(r["erkaklar"], 0)
            self.assertEqual(r["ayollar"], 0)

    def test_boundary_age_14(self):
        self._make_yosh(14, "Мужской", name="Young")
        result = _build_age_gender_distribution()
        age_row = next(r for r in result if r["age"] == 14)
        self.assertEqual(age_row["erkaklar"], 1)

    def test_boundary_age_30(self):
        self._make_yosh(30, "Женский", name="Old")
        result = _build_age_gender_distribution()
        age_row = next(r for r in result if r["age"] == 30)
        self.assertEqual(age_row["ayollar"], 1)

    def test_out_of_range_age_not_included(self):
        """Age 13 should not appear in results."""
        today = timezone.localdate()
        birth_13 = today.replace(year=today.year - 13) - timedelta(days=1)
        Yosh.objects.create(
            fullname="TooYoung",
            birth_date=birth_13,
            jshshir="300000000000131",
            address="Test",
            mahalla=self.mahalla,
            school_gender="Мужской",
        )
        result = _build_age_gender_distribution()
        ages = [r["age"] for r in result]
        self.assertNotIn(13, ages)

    def test_empty_genders_counted_as_zero(self):
        """Yosh records with empty school_gender should not count for either gender."""
        self._make_yosh(18, "", name="Unknown")
        result = _build_age_gender_distribution()
        age_row = next(r for r in result if r["age"] == 18)
        self.assertEqual(age_row["erkaklar"], 0)
        self.assertEqual(age_row["ayollar"], 0)

    def test_multiple_records_same_age(self):
        for i in range(5):
            self._make_yosh(19, "Мужской", name=f"Male{i}")
        for i in range(3):
            self._make_yosh(19, "Женский", name=f"Female{i}")
        result = _build_age_gender_distribution()
        age_row = next(r for r in result if r["age"] == 19)
        self.assertEqual(age_row["erkaklar"], 5)
        self.assertEqual(age_row["ayollar"], 3)
