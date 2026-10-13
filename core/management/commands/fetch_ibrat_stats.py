from django.core.management.base import BaseCommand

from core.ibrat import fetch_and_store_ibrat_snapshot


class Command(BaseCommand):
    help = "Ibrat Farzandlari statistikasi snapshotini yangilaydi"

    def handle(self, *args, **options):
        snapshot, error = fetch_and_store_ibrat_snapshot()
        if error:
            self.stderr.write(self.style.ERROR(f"Xatolik: {error}"))
            return
        self.stdout.write(self.style.SUCCESS(f"OK: {snapshot.snapshot_date}"))
