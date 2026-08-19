from django.core.management.base import BaseCommand
from core.models import Mahalla
from eco_energiya.models import SolarPanel


class Command(BaseCommand):
    help = "Barcha mahallalar uchun bo'sh SolarPanel yozuvlarini yaratadi"

    def handle(self, *args, **options):
        created = 0
        for mahalla in Mahalla.objects.all():
            _, was_created = SolarPanel.objects.get_or_create(mahalla=mahalla)
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"{created} ta SolarPanel yaratildi"))
