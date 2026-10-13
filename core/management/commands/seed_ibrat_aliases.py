from django.core.management.base import BaseCommand

from core.models import Mahalla, IbratFarzandlariMahallaAlias
from core.ibrat import _normalize_name


# (Core Mahalla nomi, API'dagi nomi)
SEED_MAPPINGS = [
    ("Al-Xorazmiy", "Al-Xorazmiy"),
    ("Aloqali koʻl", "Aloqali koʻl"),
    ("Amudaryo", "Amudaryo"),
    ("Barkamol avlod", "Barkamol avlod"),
    ("Beshta", "Beshta"),
    ("Bogi eram", "Bogi eram"),
    ("Bogʻdor", "Bogʻdor"),
    ("Bogʻirogʻlar", "Bogʻirogʻlar"),
    ("Boʻston", "Boʻston"),
    ("Buyuk Simo", "Buyuk Simo"),
    ("Buyuk ajdodlar", "Buyuk ajdodlar"),
    ("Gulzor", "Gulzor"),
    ("G‘.G‘ofur", "G‘.G‘ulom mahallasi"),
    ("Ishchilar", "Ishchilar"),
    ("Istiqlol", "Istiqlol"),
    ("Jaloladdin Manguberdi", "J.Manguberdi maxallasi"),
    ("Juvarxos", "Juvarxoz mahallasi"),
    ("Kamolot", "Kamolot"),
    ("Karvak", "Karvak"),
    ("Kirtepa", "Kirtepa"),
    ("Ming otliqlar", "Ming otliqlar"),
    ("Munis Xorazmiy", "Munis Xorazmiy"),
    ("Mustaqillik", "Mustaqillik"),
    ("Muxomon", "Muxomon"),
    ("Navroʻz", "Navroʻz"),
    ("Obod zamin", "Obod zamin"),
    ("Oq maydon", "Oq maydon"),
    ("Otaliq", "Otaliq"),
    ("Otaliq", "Ataliq mahallasi"),
    ("Ovshar", "Ovshar"),
    ("Oybek nomli", "Oybek nomli"),
    ("Paxlavon Maxmud", "Paxlovon Maxmud maxallasi"),
    ("Pichoqchi", "Pichoqchi"),
    ("Qovunchi", "Qovunchi"),
    ("Sanoat", "Sanoat"),
    ("Shoduxurram", "Shoduxurram"),
    ("Shovot", "Shovot"),
    ("Shukrona", "Shukrona"),
    ("Sulaymon qalʻasi", "Sulaymon qalʻʻasi"),
    ("Taraqqiyot", "Taraqqiyot"),
    ("Temirchi maskani", "Temirchi maskani"),
    ("Yangi xayot", "Yangi xayot"),
    ("Yangibozor", "Yangibozor"),
    ("Yangiobod", "Yangiobod"),
    ("Yuqori Shovot", "Yuqori Shovot"),
    ("Zehnli", "Zehnli"),
    ("Ziyolilar", "Ziyolilar"),
]


class Command(BaseCommand):
    help = "Ibrat Farzandlari mahalla moslashlarini to'ldiradi."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        missing = []

        for core_name, api_name in SEED_MAPPINGS:
            mahalla = Mahalla.objects.filter(name=core_name).first()
            if not mahalla:
                # Agar Core nomda apostrof farqi bo'lsa
                for m in Mahalla.objects.all():
                    if _normalize_name(m.name) == _normalize_name(core_name):
                        mahalla = m
                        break

            if not mahalla:
                missing.append(core_name)
                continue

            api_norm = _normalize_name(api_name)
            alias, was_created = IbratFarzandlariMahallaAlias.objects.update_or_create(
                api_norm=api_norm,
                defaults={"api_name": api_name.strip(), "mahalla": mahalla},
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Yaratildi: {created}, yangilandi: {updated}"))
        if missing:
            self.stdout.write(self.style.WARNING("Topilmagan mahallalar: " + ", ".join(missing)))
