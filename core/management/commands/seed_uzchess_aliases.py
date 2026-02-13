from django.core.management.base import BaseCommand

from core.models import Mahalla, UzchessMahallaAlias


SEED_MAPPINGS = [
    ("Al-Xorazmiy", "Al-Xorazmiy nomli MFY"),
    ("Aloqali ko‘l", "“Aloqali ko‘l” MFY"),
    ("Amudaryo", "“Amudaryo” MFY"),
    ("Barkamol avlod", "Barkamol avlod MFY"),
    ("Beshta", "“Beshta” MFY"),
    ("Bogi eram", "“Bog'i eram” MFY"),
    ("Bog‘dor", "“Bog'dor” MFY"),
    ("Bog‘irog‘lar", "“Bog'irog'lar” MFY"),
    ("Bo‘ston", "“Bo'ston” MFY"),
    ("Buyuk Simo", "“Buyuk Simo” MFY"),
    ("Buyuk ajdodlar", "“Buyuk ajdodAb-u” MFY"),
    ("Gulzor", "“Gulzor” MFY"),
    ("G‘.G‘ofur", "G'.G'ulom nomli MFY"),
    ("Ishchilar", "“Ishchilar” MFY"),
    ("Istiqlol", "“Istiqlol” MFY"),
    ("Jaloladdin Manguberdi", "J. Manguberdi nomli MFY"),
    ("Juvarxos", "“Juvarxos” MFY"),
    ("Kamolot", "“Kamolot” MFY"),
    ("Karvak", "“Karvak” MFY"),
    ("Kirtepa", "“Kirtepa” MFY"),
    ("Ming otliqlar", "“Ming otliqlar” MFY"),
    ("Munis Xorazmiy", "“Munis Xorazmiy” MFY"),
    ("Mustaqillik", "“Mustaqillik” MFY"),
    ("Muxomon", "“Muxomon” MFY"),
    ("Navro‘z", "“Navro'z” MFY"),
    ("Obod zamin", "Obod zamin MFY"),
    ("Oq maydon", "“Oq maydon” MFY"),
    ("Otaliq", "“Otaliq” MFY"),
    ("Ovshar", "“Ovshar” MFY"),
    ("Oybek nomli", "Oybek MFY"),
    ("Paxlavon Maxmud", "“Paxlavon maxmud” MFY"),
    ("Pichoqchi", "“Pichoqchi” MFY"),
    ("Qovunchi", "“Qovunchi” MFY"),
    ("Sanoat", "“Sanoat” MFY"),
    ("Shoduxurram", "“Shoduxurram” MFY"),
    ("Shovot", "“Shovot” MFY"),
    ("Shukrona", "“Shukurona” MFY"),
    ("Sulaymon qal’asi", "“Sulaymon qal’asi” MFY"),
    ("Taraqqiyot", "Tarakkiyot MFY"),
    ("Temirchi maskani", "“Temirchi maskani” MFY"),
    ("Yangi xayot", "“Yangi-hayot” MFY"),
    ("Yangibozor", "“Yangibozor” MFY"),
    ("Yangiobod", "“Yangiobod” MFY"),
    ("Yuqori Shovot", "“Yuqori Shovot” MFY"),
    ("Zehnli", "“Zehnli” MFY"),
    ("Ziyolilar", "Ziyolilar MFY"),
]


class Command(BaseCommand):
    help = "UzChess mahalla moslashlarini qo'lda berilgan ro'yxat bo'yicha to'ldiradi."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        missing = []

        for core_name, api_name in SEED_MAPPINGS:
            mahalla = Mahalla.objects.filter(name=core_name).first()
            if not mahalla:
                missing.append(core_name)
                continue

            alias, was_created = UzchessMahallaAlias.objects.update_or_create(
                api_norm=api_name.strip(),
                defaults={"api_name": api_name.strip(), "mahalla": mahalla},
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Yaratildi: {created}, yangilandi: {updated}"))
        if missing:
            self.stdout.write(self.style.WARNING("Topilmagan mahallalar: " + ", ".join(missing)))
