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
    Alias = apps.get_model("core", "MutolaaMahallaAlias")
    Stat = apps.get_model("core", "MutolaaMahallaStat")

    mapping = [
        ("m.f.y AL-XORAZMIY", "Al-Xorazmiy"),
        ("m.f.y ALOQALI KOʻL", "Aloqali koʻl"),
        ("m.f.y AMUDARYO", "Amudaryo"),
        ("m.f.y BARKAMOL AVLOD", "Barkamol avlod"),
        ("m.f.y BESHTA", "Beshta"),
        ("m.f.y BOGʻIERAM", "Bogi eram"),
        ("m.f.y BOGʻDOR", "Bogʻdor"),
        ("m.f.y BOGʻIROGʻLAR", "Bogʻirogʻlar"),
        ("m.f.y BOʻSTON", "Boʻston"),
        ("m.f.y BUYUK-SIYMO", "Buyuk Simo"),
        ("m.f.y BUYUK-AJDODLAR", "Buyuk ajdodlar"),
        ("m.f.y GULZOR", "Gulzor"),
        ("m.f.y GʻOFUR GʻULOM", "Gʻ.Gʻofur"),
        ("m.f.y ISHCHILAR", "Ishchilar"),
        ("m.f.y ISTIQLOL", "Istiqlol"),
        ("m.f.y JALOLADDIN MANGUBERDI", "Jaloladdin Manguberdi"),
        ("m.f.y JUVARXOS", "Juvarxos"),
        ("m.f.y KAMOLOT", "Kamolot"),
        ("m.f.y KARVAK", "Karvak"),
        ("m.f.y QIRTEPA", "Kirtepa"),
        ("m.f.y MING OTLIQLAR", "Ming otliqlar"),
        ("m.f.y MUNIS XORAZMIY", "Munis Xorazmiy"),
        ("m.f.y MUSTAQILLIK", "Mustaqillik"),
        ("m.f.y MUXOMON", "Muxomon"),
        ("m.f.y NAVROʻZ", "Navroʻz"),
        ("m.f.y OBOD ZAMIN", "Obod zamin"),
        ("m.f.y OQ MAYDON", "Oq maydon"),
        ("m.f.y OTALIQ", "Otaliq"),
        ("m.f.y OVSHAR", "Ovshar"),
        ("m.f.y OYBEK", "Oybek nomli"),
        ("m.f.y PAXLAVON MAXMUD", "Paxlavon Maxmud"),
        ("m.f.y PICHOQCHI", "Pichoqchi"),
        ("m.f.y QOVUNCHI", "Qovunchi"),
        ("m.f.y SANOAT", "Sanoat"),
        ("m.f.y SHODUHURRAM", "Shoduxurram"),
        ("m.f.y SHOVOT", "Shovot"),
        ("m.f.y SHUKRONA", "Shukrona"),
        ("m.f.y SULAYMON QALʻASI", "Sulaymon qalʻasi"),
        ("m.f.y TARAQQIYOT", "Taraqqiyot"),
        ("m.f.y TEMIRCHI MASKAN", "Temirchi maskani"),
        ("m.f.y YANGI XAYOT", "Yangi xayot"),
        ("m.f.y YANGIBOZAR", "Yangibozor"),
        ("m.f.y YANGI OBOD", "Yangiobod"),
        ("m.f.y YUQORI-SHOVOT", "Yuqori Shovot"),
        ("m.f.y ZEHNLI", "Zehnli"),
        ("m.f.y ZIYOLILAR", "Ziyolilar"),
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
        api_norm = _normalize(stat.mahalla_name)
        mahalla_id = alias_map.get(api_norm)
        if mahalla_id:
            stat.mahalla_id = mahalla_id
            stat.save(update_fields=["mahalla"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_mutolaa_alias"),
    ]

    operations = [
        migrations.RunPython(seed_aliases, migrations.RunPython.noop),
    ]
