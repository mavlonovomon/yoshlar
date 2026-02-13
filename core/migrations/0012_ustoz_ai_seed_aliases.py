from django.db import migrations


def _normalize(value: str) -> str:
    import re
    cleaned = value.lower()
    cleaned = cleaned.replace("mahalla", "")
    cleaned = re.sub(r"\bm\.?f\.?y\b", "", cleaned)
    cleaned = re.sub(r"\bmf\b", "", cleaned)
    cleaned = cleaned.replace("ʻ", "")
    cleaned = cleaned.replace("ʼ", "")
    cleaned = cleaned.replace("’", "")
    cleaned = cleaned.replace("‘", "")
    cleaned = cleaned.replace("`", "")
    cleaned = cleaned.replace("'", "")
    cleaned = cleaned.replace("oʻ", "o")
    cleaned = cleaned.replace("gʻ", "g")
    cleaned = re.sub(r"[^a-z0-9]+", "", cleaned)
    return cleaned.strip()


def seed_aliases(apps, schema_editor):
    Mahalla = apps.get_model("core", "Mahalla")
    Alias = apps.get_model("core", "UstozAiMahallaAlias")
    Stat = apps.get_model("core", "UstozAiMahallaStat")

    mapping = [
        ("Al-Xorazmiy nomli MFY", "Al-Xorazmiy"),
        ("“Kirtepa” MFY", "Kirtepa"),
        ("Barkamol avlod MFY", "Barkamol avlod"),
        ("“Muxomon” MFY", "Muxomon"),
        ("“Shukurona” MFY", "Shukrona"),
        ("“Juvarxos” MFY", "Juvarxos"),
        ("“Karvak” MFY", "Karvak"),
        ("Ziyolilar MFY", "Ziyolilar"),
        ("“Oq maydon” MFY", "Oq maydon"),
        ("“Bog'i eram” MFY", "Bogi eram"),
        ("“Paxlavon maxmud” MFY", "Paxlavon Maxmud"),
        ("“Yangiobod” MFY", "Yangiobod"),
        ("“Zehnli” MFY", "Zehnli"),
        ("“Aloqali ko'l” MFY", "Aloqali koʻl"),
        ("“Beshta” MFY", "Beshta"),
        ("“Pichoqchi” MFY", "Pichoqchi"),
        ("Tarakkiyot MFY", "Taraqqiyot"),
        ("“Yangibozor” MFY", "Yangibozor"),
        ("“Bog'dor” MFY", "Bogʻdor"),
        ("Oybek MFY", "Oybek nomli"),
        ("“Temirchi maskani” MFY", "Temirchi maskani"),
        ("“Sanoat” MFY", "Sanoat"),
        ("“Amudaryo” MFY", "Amudaryo"),
        ("“Bog'irog'lar” MFY", "Bogʻirogʻlar"),
        ("“Kamolot” MFY", "Kamolot"),
        ("“Ming otliqlar” MFY", "Ming otliqlar"),
        ("“Buyuk ajdodAb-u” MFY", "Buyuk ajdodlar"),
        ("“Sulaymon qal’asi” MFY", "Sulaymon qalʻasi"),
        ("“Ishchilar” MFY", "Ishchilar"),
        ("G'.G'ulom nomli MFY", "Gʻ.Gʻofur"),
        ("“Yuqori Shovot” MFY", "Yuqori Shovot"),
        ("“Buyuk Simo” MFY", "Buyuk Simo"),
        ("“Navro'z” MFY", "Navroʻz"),
        ("“Otaliq” MFY", "Otaliq"),
        ("“Qovunchi” MFY", "Qovunchi"),
        ("“Munis Xorazmiy” MFY", "Munis Xorazmiy"),
        ("“Gulzor” MFY", "Gulzor"),
        ("“Shovot” MFY", "Shovot"),
        ("“Ovshar” MFY", "Ovshar"),
        ("“Shoduxurram” MFY", "Shoduxurram"),
        ("“Mustaqillik” MFY", "Mustaqillik"),
        ("Obod zamin MFY", "Obod zamin"),
        ("“Istiqlol” MFY", "Istiqlol"),
        ("J. Manguberdi nomli MFY", "Jaloladdin Manguberdi"),
        ("“Yangi-hayot” MFY", "Yangi xayot"),
        ("“Bo'ston” MFY", "Boʻston"),
    ]

    mahalla_by_name = {m.name: m for m in Mahalla.objects.all()}
    for api_name, core_name in mapping:
        api_norm = _normalize(api_name)
        mahalla = mahalla_by_name.get(core_name)
        alias, created = Alias.objects.get_or_create(
            api_norm=api_norm,
            defaults={"api_name": api_name, "mahalla": mahalla},
        )
        if not created:
            alias.api_name = api_name
            alias.mahalla = mahalla
            alias.save(update_fields=["api_name", "mahalla", "last_seen"])

    alias_map = {a.api_norm: a.mahalla_id for a in Alias.objects.all() if a.mahalla_id}
    for stat in Stat.objects.filter(mahalla__isnull=True):
        api_norm = _normalize(stat.area_name)
        mahalla_id = alias_map.get(api_norm)
        if mahalla_id:
            stat.mahalla_id = mahalla_id
            stat.save(update_fields=["mahalla"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_ustoz_ai_models"),
    ]

    operations = [
        migrations.RunPython(seed_aliases, migrations.RunPython.noop),
    ]
