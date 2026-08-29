from django.core.management.base import BaseCommand
from django.db.models import Q
from core.models import Yosh


class Command(BaseCommand):
    help = "Bo'sh jins (school_gender) maydonlarini JSHSHIR va F.I.Sh asosida aniqlab to'ldiradi."

    def handle(self, *args, **options):
        qs = Yosh.objects.filter(school_gender="")
        total = qs.count()
        self.stdout.write(f"Jami bo'sh jins: {total}")

        updated = 0

        # JSHSHIR boshlanishi 5 -> erkak
        n = qs.filter(jshshir__startswith="5").update(school_gender="Мужской")
        updated += n
        self.stdout.write(f"  5->Мужской: {n}")

        # JSHSHIR boshlanishi 6 -> ayol
        n = qs.filter(jshshir__startswith="6").update(school_gender="Женский")
        updated += n
        self.stdout.write(f"  6->Женский: {n}")

        # Qolganlar: 3 va 4 boshlanuvchilar - F.I.Sh asosida
        remaining = qs.filter(
            Q(jshshir__startswith="3") | Q(jshshir__startswith="4") | ~Q(jshshir__regex=r"^[0-9]")
        )
        self.stdout.write(f"  Qolgan (nom asosida aniqlash): {remaining.count()}")

        batch_updated = 0
        for yosh in remaining.iterator():
            gender = Yosh.detect_gender(yosh.fullname, yosh.jshshir)
            if gender:
                Yosh.objects.filter(pk=yosh.pk).update(school_gender=gender)
                batch_updated += 1

        updated += batch_updated
        self.stdout.write(self.style.SUCCESS(f"Jami yangilandi: {updated} / {total}"))
