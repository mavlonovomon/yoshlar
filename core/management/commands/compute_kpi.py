from calendar import monthrange
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import User
from core.services.kpi_service import build_kpi_rows, compute_and_store_kpi_snapshots


class Command(BaseCommand):
    help = "Yetakchilar KPI snapshotlarini hisoblaydi va saqlaydi."

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=str,
            help='Hisoblash oyi (YYYY-MM), masalan: 2026-02',
        )
        parser.add_argument(
            '--from-date',
            type=str,
            help='Boshlanish sana (YYYY-MM-DD). --month bilan birga berilmaydi.',
        )
        parser.add_argument(
            '--to-date',
            type=str,
            help='Tugash sana (YYYY-MM-DD). --month bilan birga berilmaydi.',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Faqat bitta yetakchi uchun hisoblash.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='DBga yozmasdan faqat hisob natijasini chiqaradi.',
        )

    def handle(self, *args, **options):
        date_from, date_to = self._resolve_period(options)
        leaders = User.objects.filter(role='YETAKCHI')
        if not options.get('dry_run'):
            leaders = leaders.filter(is_active=True)

        user_id = options.get('user_id')
        if user_id:
            leaders = leaders.filter(id=user_id)

        leaders = list(leaders.order_by('full_name', 'username'))
        if not leaders:
            raise CommandError("Hisoblash uchun yetakchi topilmadi.")

        self.stdout.write(f"Davr: {date_from} - {date_to}")
        self.stdout.write(f"Yetakchilar soni: {len(leaders)}")

        if options.get('dry_run'):
            rows = build_kpi_rows(leaders, from_date=date_from, to_date=date_to)
            rows = sorted(rows, key=lambda item: item['total_score'], reverse=True)
            self.stdout.write(self.style.WARNING("Dry-run rejim: DBga yozilmadi."))
            for row in rows[:10]:
                leader = row['leader']
                name = leader.full_name or leader.username
                self.stdout.write(
                    f"- {name}: {row['total_score']:.2f} "
                    f"(Q:{row['coverage_score'] or 0:.2f}, B:{row['employment_score'] or 0:.2f}, "
                    f"X:{row['risk_score'] or 0:.2f}, I:{row['execution_score'] or 0:.2f}, T:{row['initiative_score'] or 0:.2f})"
                )
            self.stdout.write(self.style.SUCCESS(f"Dry-run tugadi. Hisoblangan qatorlar: {len(rows)}"))
            return

        snapshots = compute_and_store_kpi_snapshots(leaders, date_from, date_to)
        self.stdout.write(self.style.SUCCESS(f"Saqlangan snapshotlar: {len(snapshots)}"))

    def _resolve_period(self, options):
        month_raw = options.get('month')
        from_raw = options.get('from_date')
        to_raw = options.get('to_date')

        if month_raw and (from_raw or to_raw):
            raise CommandError("--month ni --from-date/--to-date bilan birga ishlatmang.")

        if month_raw:
            try:
                year_str, month_str = month_raw.split('-', 1)
                year = int(year_str)
                month = int(month_str)
                first_day = date(year, month, 1)
                last_day = date(year, month, monthrange(year, month)[1])
            except (ValueError, TypeError):
                raise CommandError("--month formati noto'g'ri. To'g'ri format: YYYY-MM")
            return first_day, last_day

        if from_raw or to_raw:
            if not from_raw or not to_raw:
                raise CommandError("--from-date va --to-date ikkalasi ham berilishi kerak.")
            try:
                first_day = date.fromisoformat(from_raw)
                last_day = date.fromisoformat(to_raw)
            except ValueError:
                raise CommandError("Sana formati noto'g'ri. To'g'ri format: YYYY-MM-DD")
            if first_day > last_day:
                raise CommandError("--from-date --to-date dan katta bo'lishi mumkin emas.")
            return first_day, last_day

        today = timezone.localdate()
        return today.replace(day=1), today
