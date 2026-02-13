from django.db import migrations


def _normalize(value: str) -> str:
    import re
    cleaned = value.lower()
    cleaned = cleaned.replace("mahalla", "")
    cleaned = re.sub(r"m\.?f\.?y", "", cleaned)
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
    cleaned = cleaned.replace("mfy", "")
    return cleaned.strip()


def seed_aliases(apps, schema_editor):
    Mahalla = apps.get_model("core", "Mahalla")
    Alias = apps.get_model("core", "UzchessMahallaAlias")
    Stat = apps.get_model("core", "UzchessMahallaStat")

    mapping = [
        ("_Ovshar_MFY", "Ovshar"),
        ("Oq_maydon_MFY", "Oq maydon"),
        ("_Karvak_MFY", "Karvak"),
        ("_Kirtepa_MFY", "Kirtepa"),
        ("_Bog_i_eram_MFY", "Bogi eram"),
        ("Barkamol avlod MFY", "Barkamol avlod"),
        ("J_Manguberdi nomli MFY", "Jaloladdin Manguberdi"),
        ("_Amudaryo_MFY", "Amudaryo"),
        ("_Bog_dor_MFY", "Bogʻdor"),
        ("Yangibozor_MFY", "Yangibozor"),
        ("_Otaliq_MFY", "Otaliq"),
        ("_Gulzor_MFY", "Gulzor"),
        ("Ziyolilar MFY", "Ziyolilar"),
        ("_Paxlavon maxmud _MFY", "Paxlavon Maxmud"),
        ("_Istiqlol_MFY", "Istiqlol"),
        ("_Shukurona_MFY", "Shukrona"),
        ("_Ming otliqlar_MFY", "Ming otliqlar"),
        ("Munis Xorazmiy _MFY", "Munis Xorazmiy"),
        ("_Buyuk Simo_MFY", "Buyuk Simo"),
        ("G_Gulom nomli MFY", "Gʻ.Gʻofur"),
        ("Al-Xorazmiy nomli MFY", "Al-Xorazmiy"),
        ("_Sulaymon qal_asi_MFY", "Sulaymon qalʻasi"),
        ("_Bo_ston_MFY", "Boʻston"),
        ("_Ishchilar_MFY", "Ishchilar"),
        ("_Temirchi maskani_MFY", "Temirchi maskani"),
        ("Aloqali ko`l MFY", "Aloqali koʻl"),
        ("_Kamolot_MFY", "Kamolot"),
        ("_Shovot_MFY", "Shovot"),
        ("_Buyuk ajdodAb-u_MFY", "Buyuk ajdodlar"),
        ("_Yuqori Shovot_MFY", "Yuqori Shovot"),
        ("_Yangibobod_MFY", "Yangiobod"),
        ("_Muxomon_MFY", "Muxomon"),
        ("_Shoduxurram_MFY", "Shoduxurram"),
        ("Sanoat_MFY", "Sanoat"),
        ("_Bog_irog_lar_MFY", "Bogʻirogʻlar"),
        ("_Navro_z_MFY", "Navroʻz"),
        ("Oybek MFY", "Oybek nomli"),
        ("_Shirin Quduq_MFY", "Shirin Quduq"),
        ("_Pichoqchi_MFY", "Pichoqchi"),
        ("Tarakkiyot MFarkiyut MFY", "Taraqqiyot"),
        ("Obod zamin MFY", "Obod zamin"),
        ("Juvarxos_MFY", "Juvarxos"),
        ("_Mustaqillik_MFY", "Mustaqillik"),
        ("_Yangi-hayot_MFY", "Yangi xayot"),
        ("_Qovunchi_MFY", "Qovunchi"),
        ("_Zehnli_MFY", "Zehnli"),
        ("_Beshta_MFY", "Beshta"),
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
        ("core", "0013_uzchess_models"),
    ]

    operations = [
        migrations.RunPython(seed_aliases, migrations.RunPython.noop),
    ]
