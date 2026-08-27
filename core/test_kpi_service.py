from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from beshtashabbus.models import FiveInitiativeEvent
from bilim_sinovi.models import TestConfig, TestResult
from ishsiz_yoshlar.models import AssistanceInfo, UnemployedYouth
from kredit_yo_naltirish.models import CreditCandidate
from migratsiya.models import MigrationMeeting, MigrationYouth
from otaliq.models import OtaliqMeeting, OtaliqYouth
from reyd.models import RaidEvent
from yoqlama.models import AttendanceRecord, AttendanceSession

from core.models import KpiColumnPref, Mahalla, Yosh
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


class ModuleFormulasTest(TestCase):
    @staticmethod
    def _aware(y, m, d, h=0, mi=0):
        return timezone.make_aware(datetime(y, m, d, h, mi))

    @classmethod
    def setUpTestData(cls):
        cls.mahalla = Mahalla.objects.create(name="Formula Mahalla")
        cls.other = Mahalla.objects.create(name="Boshqa Mahalla")
        cls.leader = get_user_model().objects.create_user(
            username="lf", full_name="Formula Yetakchi", role="YETAKCHI", mahalla=cls.mahalla,
        )
        cls.period_from = date(2026, 1, 1)
        cls.period_to = date(2026, 3, 31)
        y1 = Yosh.objects.create(
            fullname="Yosh 1", mahalla=cls.mahalla,
            birth_date=date(2000, 1, 1), jshshir="1111111111111", address="Test address 1",
        )
        y2 = Yosh.objects.create(
            fullname="Yosh 2", mahalla=cls.mahalla,
            birth_date=date(2000, 2, 2), jshshir="2222222222222", address="Test address 2",
        )
        y3 = Yosh.objects.create(
            fullname="Yosh 3", mahalla=cls.other,
            birth_date=date(2000, 3, 3), jshshir="3333333333333", address="Test address 3",
        )
        o1 = OtaliqYouth.objects.create(yosh=y1, category='PROBATSIYA')
        o2 = OtaliqYouth.objects.create(yosh=y2, category='PROBATSIYA')
        otaliq_other = OtaliqYouth.objects.create(yosh=y3, category='PROBATSIYA')
        OtaliqMeeting.objects.create(otaliq_youth=o1, meeting_date=cls._aware(2026, 1, 10, 10, 0))
        m1 = MigrationYouth.objects.create(
            yosh=y1, departure_date=date(2026, 1, 1),
            destination_country="O'zbekiston", reason='ISH',
        )
        m2 = MigrationYouth.objects.create(
            yosh=y2, departure_date=date(2026, 1, 1),
            destination_country="O'zbekiston", reason='ISH',
        )
        MigrationMeeting.objects.create(migration_youth=m1, meeting_date=cls._aware(2026, 1, 15, 10, 0))
        u1 = UnemployedYouth.objects.create(
            yosh=y1, year=2026, category='OLIY', otm_name='Test OTM', direction='Test',
        )
        u2 = UnemployedYouth.objects.create(
            yosh=y2, year=2026, category='OLIY', otm_name='Test OTM', direction='Test',
        )
        AssistanceInfo.objects.create(unemployed_youth=u1, provided=True, assistance_type='ISH', date_provided=date(2026, 2, 1))
        RaidEvent.objects.create(title="R1", mahalla=cls.mahalla, event_date=date(2026, 1, 15))
        RaidEvent.objects.create(title="R2", mahalla=cls.mahalla, event_date=date(2026, 2, 15))
        FiveInitiativeEvent.objects.create(direction='SPORT', title="F1", event_date=date(2026, 1, 10), mahalla=cls.mahalla, coverage=40)
        FiveInitiativeEvent.objects.create(direction='SPORT', title="F2", event_date=date(2026, 2, 10), mahalla=cls.mahalla, coverage=20)
        CreditCandidate.objects.create(yosh=y1, stage='APPROVED')
        CreditCandidate.objects.create(yosh=y2, stage='NOMINATION')
        from intizom_jazo.models import DisciplineAction
        DisciplineAction.objects.create(employee=cls.leader, action_type='OGOHLANTIRISH', action_date=date(2026, 2, 1))
        sess1 = AttendanceSession.objects.create(session_type='BOSHQA', session_date=cls._aware(2026, 2, 1, 9, 0))
        sess2 = AttendanceSession.objects.create(session_type='YIGILISH', session_date=cls._aware(2026, 2, 15, 9, 0))
        AttendanceRecord.objects.create(session=sess1, leader=cls.leader, status='ON_TIME')
        AttendanceRecord.objects.create(session=sess2, leader=cls.leader, status='LATE')
        tcfg = TestConfig.objects.create(
            title="T",
            start_time=cls._aware(2026, 1, 1),
            end_time=cls._aware(2026, 4, 1),
            duration_minutes=10,
        )
        tr = TestResult.objects.create(
            user=cls.leader, test_config=tcfg, score=8, total_questions=10,
            finished_at=cls._aware(2026, 2, 5, 11, 0),
        )
        TestResult.objects.filter(pk=tr.pk).update(started_at=cls._aware(2026, 2, 5, 10, 0))
        cls.leader_id = cls.leader.id

    def _row(self):
        rows = build_module_rows(
            [self.leader], from_date=self.period_from, to_date=self.period_to
        )
        return rows[0]

    def test_otaliq_pct(self):
        self.assertEqual(self._row()["modules"]["otaliq"]["pct"], 50.0)

    def test_migratsiya_pct(self):
        self.assertEqual(self._row()["modules"]["migratsiya"]["pct"], 50.0)

    def test_ishsiz_pct(self):
        self.assertEqual(self._row()["modules"]["ishsiz"]["pct"], 50.0)

    def test_reyd_and_reyd_otkazilishi(self):
        row = self._row()
        # reyd = 2 tadbir / max(2) = 100%
        self.assertEqual(row["modules"]["reyd"]["pct"], 100.0)
        # reyd_otkazilishi = 2 distinct oy (yanvar, fevral) / 3 oy (yanvar-mart) = 66.7
        self.assertEqual(row["modules"]["reyd_otkazilishi"]["pct"], 66.7)

    def test_besh_tashabbus_pct(self):
        self.assertEqual(self._row()["modules"]["besh_tashabbus"]["pct"], 100.0)

    def test_yoqlama_pct(self):
        # (1 on_time + 0 excused + 1 late*0.6) / 2 = 0.8
        self.assertEqual(self._row()["modules"]["yoqlama"]["pct"], 80.0)

    def test_kredit_pct(self):
        self.assertEqual(self._row()["modules"]["kredit"]["pct"], 50.0)

    def test_intizom_pct(self):
        # 100 - 5 (ogohlantirish)
        self.assertEqual(self._row()["modules"]["intizom"]["pct"], 95.0)

    def test_bilim_pct(self):
        self.assertEqual(self._row()["modules"]["bilim"]["pct"], 80.0)
