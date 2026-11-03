import openpyxl
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Yosh
from ishsiz_yoshlar.models import UnemployedYouth, ResponsibleLeader


class Command(BaseCommand):
    help = "OTM faylining G ustunidagi mas'ul rahbarlarni bazadagi yoshlarga biriktirish"

    def add_arguments(self, parser):
        parser.add_argument(
            '--excel_path',
            type=str,
            default=r'c:\Users\Genius007\Desktop\Хоразм ОТМ номма-ном 13540 нафар (2).xlsx',
            help='Excel fayl yo\'li'
        )

    def handle(self, *args, **options):
        excel_path = options['excel_path']
        self.stdout.write(f"Excel fayl ochilmoqda: {excel_path}")

        wb = openpyxl.load_workbook(excel_path, data_only=True)
        sheet_name = 'Номма-ном' if 'Номма-ном' in wb.sheetnames else wb.sheetnames[0]
        ws = wb[sheet_name]
        self.stdout.write(f"Faol varaq: {ws.title} (Jami qatorlar: {ws.max_row})")

        # G ustunidagi lavozimlarni ResponsibleLeader ID lariga moslashtirish xaritasi
        leader_mapping = {
            # 1. Mahalla uyushmasi
            "Hazorasp tuman O‘zbekiston mahallari uyushmasi bo‘limi boshlig‘i": 1,
            # 2. Irrigatsiya
            "Hazorasp tumani Irrigatsiya bo'limi boshlig'i": 2,
            # 3. Hokim o'rinbosarlari
            "Hazorasp tumani hokimining birinchi o‘rinbosari": 43,
            "Hazorasp tumani hokimining o‘rinbosari, investitsiyalar va tashqi savdo bo‘limi boshlig‘i": 3,
            "Hazorasp tumani hokimining o‘rinbosari": 3,
            "Hazorasp tumani hokimining o‘rinosari": 4,
            "Hazorasp tumani hokimining o‘rinbosari, oila va xotin-qizlar bo‘limi boshlig‘i": 4,
            "Hazorasp tuman hokimi o'rinbosari": 51,
            "Hazorasp tuman hokimining o'rinbosari": 20,
            "Viloyat hokimining o‘rinbosari": 18,
            "Viloyat hokimining qishloq va suv xo‘jaligi masalalari bo‘yicha o‘rinbosari": 18,
            # 4. Hokim
            "Hazorasp tumani hokimi": 36,
            # 5. Kadastr
            "Kadastr agentligining Hazorasp tumani bo‘limi boshlig‘i": 5,
            "Kadastr agentligi Xorazm viloyati boshqarmasi boshlig‘i": 45,
            "Hazorasp Kadastrlar palatasi rahbari": 52,
            "Hazorasp tuman kadastr palatasi boʻlimi boshligʻi": 52,
            # 6. Elektr, suv, gaz, yo'l, chiqindi, ko'mir, transport
            'Hazorasp tumani "Xorazm hududiy elektr tarmoqlari" AJ bo‘limi boshlig‘i': 7,
            "Xorazm suv ta’minoti MCHJ Hazorasp tumani bo‘limi": 8,
            "Hazorasp tuman \"Hududgaz Xorazm\" gaz taminoti bo'limi boshlig'i": 26,
            "Hazorasp tumani “Hududgaz Xorazm” gaz ta’minoti bo‘limi boshlig‘i": 26,
            "Hazorasp tumani “Toza hudud” unitar korxonasi boshlig‘i": 13,
            "Hazorasp tumani ko‘mir tarqatish shoxobchasi rahbari": 15,
            "Hazorasp tumani “Xorazmavtoyo‘l” hududiy yo‘llardagi foydalanish davlat tashkiloti bo‘limi boshlig‘i": 22,
            "Xorazm viloyat transport boshqarmasi boshlig'i": 53,
            # 7. Veterenariya, fermerlar, agroinspeksiya, qishloq xo'jaligi, ekologiya
            "Hazorasp tuman veterenariya bo‘limi boshlig‘i": 11,
            "Hazorasp tuman veterinariya bo‘limi boshlig‘i": 11,
            "Hazorasp tumani fermerlar kengashi raisi": 16,
            "Hazorasp tumani qishloq xo‘jaligi bo‘limi boshlig‘i": 32,
            "Hazorasp tumani ekologiya, atrof-muhitni muhofaza qilish va iqlim o‘zgarishi bo‘limi boshlig‘i": 49,
            "Ҳазорасп туман Агроинспексия бўлим бошлиғи в.в.б": 50,
            "Hazorasp tumani Agro inspeksiya rahbari": 50,
            # 8. Arxitektura
            "Hazorasp tuman arxitektura va qurilish bo‘limi boshlig‘i": 21,
            # 9. Banklar
            'Hazorasp tumani "Xalq banki" bo‘limi boshlig‘i': 23,
            "Hazorasp tumani “Agro bank” bo‘limi boshlig‘i": 33,
            'Hazorasp tumani "Milliy bank" bo‘limi boshlig‘i': 40,
            'Hazorasp tumani "Asaka bank" bo‘limi boshlig‘i': 44,
            # 10. Savdo-sanoat, soliq, iqtisodiyot, bandlik
            "Savdo-sanoat palatasi Hazorasp tumani bo‘limi boshlig‘i": 27,
            "Savdo-sanoat palatasi viloyat boshqarmasi boshlig‘i": 47,
            "Hazorasp tumani soliq inspeksiya boshlig‘i": 28,
            "Hazorasp tumani iqtisodiyot va moliya bo‘limi boshlig‘i": 35,
            "Hazorasp tumani moliya va iqtisodiyot bo‘limi boshlig‘ining birinchi o‘rinbosari": 58,
            "Hazorasp tumani kambag‘allikni qisqartirish va bandlik bo‘limi boshlig‘i": 46,
            # 11. Ta'lim, yoshlar, tibbiyot, SEO, inson
            "Hazorasp tuman maktabgacha va maktab talimi bo‘limi boshlig‘i": 29,
            "Hazorasp tuman maktabgacha va maktab ta’limi bo‘limi boshlig‘i": 29,
            "Hazorasp tumani Yoshlar ishlari bo'limi rahbari": 34,
            "Hazorasp tuman Yoshlar ishlari bo‘limi boshlig‘i": 34,
            "Hazorasp tumani sog‘liqni saqlash bo‘limi boshlig‘i v.b.": 30,
            "Hazorasp tumani sog‘liqni saqlash bo‘limi boshlig‘i": 30,
            'Hazorasp tumani "Inson" ijtimoiy xizmatlar markazi direktori': 37,
            "Hazorasp tuman SEO va JSX boshlig‘i": 39,
            "O‘zbekiston mahallalari uyushmasi Xorazm viloyati boshqarmasi boshlig‘i": 42,
            # 12. Hunarmandlar
            "Hunarmandlar uyushmasi boshlig‘i": 63,
            # 13. Urganch davlat tibbiyot instituti
            "Urganch davlat tibbiyot instituti  2-Davolash fakulteti dekanati dekani": 64,
            "Urganch davlat tibbiyot instituti 2-Davolash fakulteti dekanati dekani": 64,
            "Urganch davlat tibbiyot instituti  Davolash fakulteti dekanati dekani": 61,
            "Urganch davlat tibbiyot instituti Davolash fakulteti dekanati dekani": 61,
            "Urganch davlat tibbiyot instituti  Ilmiy ishlar va innovatsiyalar bo‘yicha prorektor": 60,
            "Urganch davlat tibbiyot instituti Ilmiy ishlar va innovatsiyalar bo‘yicha prorektor": 60,
            "Urganch davlat tibbiyot instituti  Moliya va iqtisod ishlari bo‘yicha prorektor": 62,
            "Urganch davlat tibbiyot instituti Moliya va iqtisod ishlari bo‘yicha prorektor": 62,
            "Urganch davlat tibbiyot instituti  O‘quv ishlari bo‘yicha prorektor": 55,
            "Urganch davlat tibbiyot instituti O‘quv ishlari bo‘yicha prorektor": 55,
            "Urganch davlat tibbiyot instituti  Pediatriya fakulteti dekanati dekani": 66,
            "Urganch davlat tibbiyot instituti Pediatriya fakulteti dekanati dekani": 66,
            "Urganch davlat tibbiyot instituti  Qo‘shma ta’lim dasturi fakulteti dekanati  dekani": 65,
            "Urganch davlat tibbiyot instituti Qo‘shma ta’lim dasturi fakulteti dekanati dekani": 65,
            "Urganch davlat tibbiyot instituti  Stomatologiya fakulteti dekanati  dekani": 67,
            "Urganch davlat tibbiyot instituti Stomatologiya fakulteti dekanati dekani": 67,
            "Urganch davlat tibbiyot instituti  Xalqaro Hamkorlik bo‘yicha prorektor": 59,
            "Urganch davlat tibbiyot instituti Xalqaro Hamkorlik bo‘yicha prorektor": 59,
            "Urganch davlat tibbiyot instituti  Xorijiy fakulteti dekanati dekani": 68,
            "Urganch davlat tibbiyot instituti Xorijiy fakulteti dekanati dekani": 68,
            "Urganch davlat tibbiyot instituti Yoshlar masalalari va  ma’naviy-ma’rifiy ishlar bo‘yicha  birinchi  prorektor": 57,
            "Urganch davlat tibbiyot instituti Yoshlar masalalari va  ma’naviy-ma’rifiy ishlar bo‘yicha birinchi prorektor": 57,
            "Urganch davlat tibbiyot instituti rektori": 56,
        }

        db_leaders = list(ResponsibleLeader.objects.all())

        def norm(s):
            if not s:
                return ''
            s = str(s).lower()
            for ch in ["'", "‘", "ʻ", "`", "’", '"', '“', '”', ' ', '-', '_', '.', ',']:
                s = s.replace(ch, '')
            return s

        def find_leader(g):
            if not g:
                return None
            g = str(g).strip()
            if g in leader_mapping:
                return ResponsibleLeader.objects.get(id=leader_mapping[g])
            gnorm = norm(g)
            for l in db_leaders:
                if norm(l.position) == gnorm:
                    return l
            for l in db_leaders:
                lnorm = norm(l.position)
                if len(lnorm) > 15 and (gnorm in lnorm or lnorm in gnorm):
                    return l
            return None

        total_processed = 0
        assigned_count = 0
        skipped_count = 0
        youth_not_found = 0
        leader_distribution = {}

        with transaction.atomic():
            for row_idx in range(5, ws.max_row + 1):
                pinfl_raw = ws.cell(row=row_idx, column=5).value
                if not pinfl_raw:
                    continue
                jshshir = str(pinfl_raw).strip()
                if len(jshshir) < 10:
                    continue

                total_processed += 1
                g_val = ws.cell(row=row_idx, column=7).value
                leader = find_leader(g_val)

                if not leader:
                    skipped_count += 1
                    continue

                # UnemployedYouth profilini topish
                uy = UnemployedYouth.objects.filter(yosh__jshshir=jshshir).first()
                if not uy:
                    youth_not_found += 1
                    continue

                uy.leader = leader
                uy.save(update_fields=['leader'])
                assigned_count += 1
                leader_distribution[leader.full_name] = leader_distribution.get(leader.full_name, 0) + 1

        self.stdout.write(self.style.SUCCESS(
            f"\n=== MAS'UL RAHBARLARNI BIRIKTIRISH YAKUNLANDI ===\n"
            f"Jami ko'rib chiqilgan yoshlar: {total_processed}\n"
            f"Mas'ul rahbar biriktirilgan yoshlar: {assigned_count}\n"
            f"Bazada rahbari mavjud bo'lmagani uchun qoldirilgan: {skipped_count}\n"
            f"Bazada yosh topilmagan: {youth_not_found}\n"
            f"Biriktirilgan rahbarlar soni: {len(leader_distribution)}"
        ))

        self.stdout.write("\nRahbarlar kesimida biriktirilgan yoshlar soni (Top-15):")
        for name, cnt in sorted(leader_distribution.items(), key=lambda x: -x[1])[:15]:
            self.stdout.write(f"  {name}: {cnt} nafar")
