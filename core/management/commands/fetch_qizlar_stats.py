from django.core.management.base import BaseCommand

from core.qizlar_akademiyasi import fetch_and_store_qizlar_snapshot


class Command(BaseCommand):
    help = "Qizlar akademiyasi statistikasi snapshotini yangilaydi"

    def handle(self, *args, **options):
        snapshot, error = fetch_and_store_qizlar_snapshot()
        if error:
            self.stderr.write(self.style.ERROR(f"Xatolik: {error}"))
            return
        self.stdout.write(self.style.SUCCESS(f"OK: {snapshot.snapshot_date}"))
