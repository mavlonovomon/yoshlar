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
from core.services.kpi_service import (
    MODULE_COLUMNS,
    MODULE_KEYS,
    build_module_rows,
    traffic_color,
)


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

    def test_module_columns_has_sixteen(self):
        self.assertEqual(len(MODULE_COLUMNS), 16)
        keys = [c["key"] for c in MODULE_COLUMNS]
        self.assertEqual(keys[0], "otaliq")
        self.assertEqual(keys[-1], "arizalar")
        arizalar = MODULE_COLUMNS[-1]
        self.assertEqual(arizalar.get("key"), "arizalar")
        self.assertEqual(arizalar.get("display"), "count_pct")
        self.assertEqual(MODULE_KEYS[-1], "arizalar")

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


class EcoEnergiyaModuleTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from eco_energiya.models import SolarPanel
        cls.mahalla = Mahalla.objects.create(name="Eco Test Mahalla")
        cls.leader = get_user_model().objects.create_user(
            username="ecoleader", full_name="Eco Leader", role="YETAKCHI", mahalla=cls.mahalla,
        )
        cls.panel = SolarPanel.objects.create(
            mahalla=cls.mahalla, is_installed=True, capacity_kw=8.5,
        )

    def test_eco_energiya_installed(self):
        rows = build_module_rows([self.leader])
        eco = rows[0]['modules']['eco_energiya']
        self.assertAlmostEqual(eco['pct'], 85.0, places=1)

    def test_eco_energiya_cap_at_100(self):
        from eco_energiya.models import SolarPanel
        self.panel.capacity_kw = 15.0
        self.panel.save()
        rows = build_module_rows([self.leader])
        eco = rows[0]['modules']['eco_energiya']
        self.assertEqual(eco['pct'], 100.0)

    def test_eco_energiya_not_installed(self):
        self.panel.is_installed = False
        self.panel.save()
        rows = build_module_rows([self.leader])
        eco = rows[0]['modules']['eco_energiya']
        self.assertEqual(eco['pct'], 0.0)

    def test_eco_energiya_no_panel(self):
        from eco_energiya.models import SolarPanel
        SolarPanel.objects.all().delete()
        mahalla2 = Mahalla.objects.create(name="No Panel")
        leader2 = get_user_model().objects.create_user(
            username="noleader", full_name="No Panel Leader", role="YETAKCHI", mahalla=mahalla2,
        )
        rows = build_module_rows([leader2])
        eco = rows[0]['modules']['eco_energiya']
        self.assertEqual(eco['pct'], 0.0)


class MegaloyihaModulesTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from core.models import (
            MutolaaStatSnapshot, MutolaaMahallaStat,
            UstozAiStatSnapshot, UstozAiMahallaStat,
            UzchessStatSnapshot, UzchessMahallaStat,
            QizlarAkademiyasiStatSnapshot, QizlarAkademiyasiMahallaStat,
        )
        cls.mahalla = Mahalla.objects.create(name="Mega Test Mahalla")
        cls.leader = get_user_model().objects.create_user(
            username="megaleader", full_name="Mega Leader", role="YETAKCHI", mahalla=cls.mahalla,
        )
        for i in range(20):
            Yosh.objects.create(
                fullname=f"Youth {i}", mahalla=cls.mahalla,
                birth_date=date(2000, 1, 1), jshshir=f"99{i:012d}", address="Test",
            )
        cls.total_yosh = 20

        snap_m = MutolaaStatSnapshot.objects.create(
            snapshot_date=date(2026, 8, 1), source_url="http://test",
        )
        MutolaaMahallaStat.objects.create(
            snapshot=snap_m, mahalla=cls.mahalla, mahalla_name="Mega Test",
            metrics={"users_total": 8},
        )

        snap_u = UstozAiStatSnapshot.objects.create(
            snapshot_date=date(2026, 8, 1), source_url="http://test",
        )
        UstozAiMahallaStat.objects.create(
            snapshot=snap_u, mahalla=cls.mahalla, area_name="Mega Test",
            metrics={"users_total": 12},
        )

        snap_c = UzchessStatSnapshot.objects.create(
            snapshot_date=date(2026, 8, 1), source_url="http://test",
        )
        UzchessMahallaStat.objects.create(
            snapshot=snap_c, mahalla=cls.mahalla, area_name="Mega Test",
            metrics={"users_total": 5},
        )

        snap_q = QizlarAkademiyasiStatSnapshot.objects.create(
            snapshot_date=date(2026, 8, 1), source_url="http://test",
        )
        QizlarAkademiyasiMahallaStat.objects.create(
            snapshot=snap_q, mahalla=cls.mahalla, area_name="Mega Test",
            metrics={"users_total": 15},
        )

    def test_mutolaa_pct(self):
        rows = build_module_rows([self.leader])
        m = rows[0]['modules']['mutolaa']
        self.assertAlmostEqual(m['pct'], 40.0, places=1)

    def test_ustoz_ai_pct(self):
        rows = build_module_rows([self.leader])
        m = rows[0]['modules']['ustoz_ai']
        self.assertAlmostEqual(m['pct'], 60.0, places=1)

    def test_uzchess_pct(self):
        rows = build_module_rows([self.leader])
        m = rows[0]['modules']['uzchess']
        self.assertAlmostEqual(m['pct'], 25.0, places=1)

    def test_qizlar_pct(self):
        rows = build_module_rows([self.leader])
        m = rows[0]['modules']['qizlar']
        self.assertAlmostEqual(m['pct'], 75.0, places=1)

    def test_mega_cap_at_100(self):
        from core.models import MutolaaStatSnapshot, MutolaaMahallaStat
        snap = MutolaaStatSnapshot.objects.create(
            snapshot_date=date(2026, 8, 2), source_url="http://test2",
        )
        MutolaaMahallaStat.objects.create(
            snapshot=snap, mahalla=self.mahalla, mahalla_name="Mega Test",
            metrics={"users_total": 50},
        )
        rows = build_module_rows([self.leader])
        m = rows[0]['modules']['mutolaa']
        self.assertEqual(m['pct'], 100.0)

    def test_mega_no_snapshot(self):
        from core.models import (
            MutolaaMahallaStat, UstozAiMahallaStat,
            UzchessMahallaStat, QizlarAkademiyasiMahallaStat,
        )
        MutolaaMahallaStat.objects.all().delete()
        UstozAiMahallaStat.objects.all().delete()
        UzchessMahallaStat.objects.all().delete()
        QizlarAkademiyasiMahallaStat.objects.all().delete()
        rows = build_module_rows([self.leader])
        for key in ['mutolaa', 'ustoz_ai', 'uzchess', 'qizlar']:
            self.assertEqual(rows[0]['modules'][key]['pct'], 0.0)

    def test_mega_latest_snapshot_used(self):
        from core.models import MutolaaStatSnapshot, MutolaaMahallaStat
        snap_old = MutolaaStatSnapshot.objects.create(
            snapshot_date=date(2026, 7, 1), source_url="http://old",
        )
        MutolaaMahallaStat.objects.create(
            snapshot=snap_old, mahalla=self.mahalla, mahalla_name="Mega Test",
            metrics={"users_total": 2},
        )
        rows = build_module_rows([self.leader])
        m = rows[0]['modules']['mutolaa']
        self.assertAlmostEqual(m['pct'], 40.0, places=1)


class ArizalarModuleTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from beshtashabbus.models import FiveInitiativeApplicationSnapshot, FiveInitiativeApplicationEntry
        cls.mahalla1 = Mahalla.objects.create(name="Ariza 1")
        cls.mahalla2 = Mahalla.objects.create(name="Ariza 2")
        cls.leader1 = get_user_model().objects.create_user(
            username="ariza1", full_name="Ariza L1", role="YETAKCHI", mahalla=cls.mahalla1,
        )
        cls.leader2 = get_user_model().objects.create_user(
            username="ariza2", full_name="Ariza L2", role="YETAKCHI", mahalla=cls.mahalla2,
        )
        snap = FiveInitiativeApplicationSnapshot.objects.create(year=2026, source_file_name="a.xlsx")
        FiveInitiativeApplicationEntry.objects.create(
            snapshot=snap, mahalla=cls.mahalla1, mahalla_name_raw="Ariza 1",
            participant_name="A", pinfl="10000000000001",
            selection_category="K1", direction="D1",
        )
        FiveInitiativeApplicationEntry.objects.create(
            snapshot=snap, mahalla=cls.mahalla1, mahalla_name_raw="Ariza 1",
            participant_name="B", pinfl="10000000000002",
            selection_category="K1", direction="D1",
        )
        FiveInitiativeApplicationEntry.objects.create(
            snapshot=snap, mahalla=cls.mahalla1, mahalla_name_raw="Ariza 1",
            participant_name="C", pinfl="10000000000001",
            selection_category="K2", direction="D2",
        )
        FiveInitiativeApplicationEntry.objects.create(
            snapshot=snap, mahalla=cls.mahalla2, mahalla_name_raw="Ariza 2",
            participant_name="D", pinfl="10000000000003",
            selection_category="K1", direction="D1",
        )

    def _rows(self):
        return {r["leader"].id: r for r in build_module_rows([self.leader1, self.leader2])}

    def test_distinct_pinfl_count_and_max_norm(self):
        rows = self._rows()
        a1 = rows[self.leader1.id]["modules"]["arizalar"]  # 3 entry, 2 distinct PINFL -> max = 2
        a2 = rows[self.leader2.id]["modules"]["arizalar"]  # 1/2
        self.assertEqual(a1["count"], 2)
        self.assertEqual(a1["total"], 2)
        self.assertEqual(a1["pct"], 100.0)
        self.assertEqual(a2["count"], 1)
        self.assertEqual(a2["pct"], round(1 / 2 * 100, 1))

    def test_no_entry_returns_zero(self):
        mahalla3 = Mahalla.objects.create(name="Ariza 3")
        leader3 = get_user_model().objects.create_user(
            username="ariza3", full_name="Ariza L3", role="YETAKCHI", mahalla=mahalla3,
        )
        rows = build_module_rows([leader3])
        a = rows[0]["modules"]["arizalar"]
        self.assertEqual(a["count"], 0)
        self.assertEqual(a["pct"], 0.0)

    def test_no_snapshot_returns_zero(self):
        from beshtashabbus.models import FiveInitiativeApplicationSnapshot
        FiveInitiativeApplicationSnapshot.objects.all().delete()
        rows = build_module_rows([self.leader2])
        a = rows[0]["modules"]["arizalar"]
        self.assertEqual(a, {"count": 0, "pct": 0.0, "total": 0})

    def test_latest_snapshot_only(self):
        """Only the most-recent snapshot (a.xlsx) counts; an older snapshot is ignored."""
        from datetime import timedelta
        from beshtashabbus.models import FiveInitiativeApplicationSnapshot, FiveInitiativeApplicationEntry
        old = FiveInitiativeApplicationSnapshot.objects.create(year=2025, source_file_name="old.xlsx")
        # Backdate so it is genuinely older than the setUpTestData snapshot
        FiveInitiativeApplicationSnapshot.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        FiveInitiativeApplicationEntry.objects.create(
            snapshot=old, mahalla=self.mahalla2, mahalla_name_raw="Ariza 2",
            participant_name="Old", pinfl="10000000000009",
            selection_category="K1", direction="D1",
        )
        FiveInitiativeApplicationEntry.objects.create(
            snapshot=old, mahalla=self.mahalla2, mahalla_name_raw="Ariza 2",
            participant_name="Older", pinfl="10000000000010",
            selection_category="K1", direction="D1",
        )
        rows = {r["leader"].id: r for r in build_module_rows([self.leader1, self.leader2])}
        # the older `old` snapshot contains 2 entries for mahalla2, a.xlsx only 1.
        # count must be 1 (latest a.xlsx wins), proving the older snapshot is ignored.
        self.assertEqual(rows[self.leader2.id]["modules"]["arizalar"]["count"], 1)
