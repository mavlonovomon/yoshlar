import openpyxl
from datetime import datetime, date
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Yosh, Mahalla
from ishsiz_yoshlar.models import UnemployedYouth


class Command(BaseCommand):
    help = "2026 II mavsum ishsiz yoshlarni Excel fayldan import qilish"

    def add_arguments(self, parser):
        parser.add_argument(
            '--excel_path',
            type=str,
            default=r'c:\Users\Genius007\Downloads\Новая таблица (1).xlsx',
            help='Excel fayl yo\'li'
        )

    def handle(self, *args, **options):
        excel_path = options['excel_path']
        self.stdout.write(f"Excel fayl ochilmoqda: {excel_path}")

        wb = openpyxl.load_workbook(excel_path, data_only=True)
        sheet_name = 'ёшлар номма ном' if 'ёшлар номма ном' in wb.sheetnames else wb.sheetnames[0]
        ws = wb[sheet_name]
        self.stdout.write(f"Faol varaq: {ws.title} (Jami qatorlar: {ws.max_row})")

        # Mahalla nomlarini mapping qilish
        mfy_mapping = {
            # Lotincha
            'al-xorazmiy': 'Al-Xorazmiy',
            'aloqali koʻl': 'Aloqali koʻl',
            'aloqali kol': 'Aloqali koʻl',
            'amudaryo': 'Amudaryo',
            'barkamol avlod': 'Barkamol avlod',
            'beshta': 'Beshta',
            'bogi eram': 'Bogi eram',
            'bogʻdor': 'Bogʻdor',
            'bogdor': 'Bogʻdor',
            'bogʻirogʻlar': 'Bogʻirogʻlar',
            'bogiroglar': 'Bogʻirogʻlar',
            'boʻston': 'Boʻston',
            'boston': 'Boʻston',
            'buyuk ajdodlar': 'Buyuk ajdodlar',
            'buyuk simo': 'Buyuk Simo',
            'gulzor': 'Gulzor',
            'gʻ.gʻofur': 'Gʻ.Gʻofur',
            'g.gofur': 'Gʻ.Gʻofur',
            'ishchilar': 'Ishchilar',
            'istiqlol': 'Istiqlol',
            'jaloladdin manguberdi': 'Jaloladdin Manguberdi',
            'juvarxos': 'Juvarxos',
            'kamolot': 'Kamolot',
            'karvak': 'Karvak',
            'kirtepa': 'Kirtepa',
            'ming otliqlar': 'Ming otliqlar',
            'munis xorazmiy': 'Munis Xorazmiy',
            'mustaqillik': 'Mustaqillik',
            'muxomon': 'Muxomon',
            'navroʻz': 'Navroʻz',
            'navroz': 'Navroʻz',
            'obod zamin': 'Obod zamin',
            'obodzamin': 'Obod zamin',
            'oq maydon': 'Oq maydon',
            'otaliq': 'Otaliq',
            'ovshar': 'Ovshar',
            'oybek': 'Oybek nomli',
            'oybek nomli': 'Oybek nomli',
            'paxlavon maxmud': 'Paxlavon Maxmud',
            'pichoqchi': 'Pichoqchi',
            'qovunchi': 'Qovunchi',
            'sanoat': 'Sanoat',
            'shoduxurram': 'Shoduxurram',
            'shovot': 'Shovot',
            'shukrona': 'Shukrona',
            'sulaymon qalʻasi': 'Sulaymon qalʻasi',
            'sulaymon qalasi': 'Sulaymon qalʻasi',
            'taraqqiyot': 'Taraqqiyot',
            'temirchi maskan': 'Temirchi maskani',
            'temirchi maskani': 'Temirchi maskani',
            'yangi xayot': 'Yangi xayot',
            'yangibozor': 'Yangibozor',
            'yangiobod': 'Yangiobod',
            'yangi obod': 'Yangiobod',
            'yuqori shovot': 'Yuqori Shovot',
            'yuqori-shovat': 'Yuqori Shovot',
            'zehnli': 'Zehnli',
            'ziyolilar': 'Ziyolilar',

            # Kirillcha
            'қиртеpa': 'Kirtepa',
            'қиртепа': 'Kirtepa',
            'қовунчи': 'Qovunchi',
            'минг отлиқлар': 'Ming otliqlar',
            'мунис хоразмий': 'Munis Xorazmiy',
            'мустақиллик': 'Mustaqillik',
            'мухомон': 'Muxomon',
            'наврўз': 'Navroʻz',
            'ободзамин': 'Obod zamin',
            'обод замин': 'Obod zamin',
            'овшар': 'Ovshar',
            'ойбек': 'Oybek nomli',
            'оқ майдон': 'Oq maydon',
            'оталиқ': 'Otaliq',
            'охунбобоев': 'Otaliq',
            'паҳлавон махмуд': 'Paxlavon Maxmud',
            'пичоқчи': 'Pichoqchi',
            'саноат': 'Sanoat',
            'сулаймон қалъаси': 'Sulaymon qalʻasi',
            'тараққиёт': 'Taraqqiyot',
            'темирчи маскан': 'Temirchi maskani',
            'шехлар': 'Temirchi maskani',
            'шовот': 'Shovot',
            'шодуҳуррам': 'Shoduxurram',
            'шукрона': 'Shukrona',
            'юқори-шоват': 'Yuqori Shovot',
            'янги обод': 'Yangiobod',
            'янги хаёт': 'Yangi xayot',
            'янгибозор': 'Yangibozor',
        }

        db_mahallas = {m.name: m for m in Mahalla.objects.all()}

        def resolve_mahalla(row_idx, raw_val):
            norm = str(raw_val or '').lower().strip()
            target_name = mfy_mapping.get(norm)
            if not target_name and norm == '#n/a':
                if row_idx == 184: target_name = 'Bogʻirogʻlar'
                elif row_idx == 262: target_name = 'Boʻston'
                elif row_idx == 434: target_name = 'Gʻ.Gʻofur'
                elif row_idx == 473: target_name = 'Juvarxos'
                elif row_idx == 480: target_name = 'Juvarxos'
                elif row_idx == 583: target_name = 'Istiqlol'
            return db_mahallas.get(target_name)

        def clean_phone(val):
            if not val:
                return ''
            first_part = str(val).replace('/', ',').split(',')[0].strip()
            if first_part.endswith('.0'):
                first_part = first_part[:-2]
            digits = ''.join(ch for ch in first_part if ch.isdigit())
            if len(digits) == 9:
                return digits
            if len(digits) == 12 and digits.startswith('998'):
                return digits[3:]
            return digits[:20]

        def get_category(c9, c10):
            c9_str = str(c9 or '').strip()
            c10_str = str(c10 or '').strip().lower()
            if c9_str == '1' or 'maktab' in c10_str or 'мактаб' in c10_str:
                return 'MAKTAB'
            if c9_str == '2' or 'otm' in c10_str or 'отм' in c10_str or 'oliy' in c10_str:
                return 'OLIY'
            if c9_str in ('3', '4') or 'kasb' in c10_str or 'касб' in c10_str:
                return 'KASBIY'
            return 'QOLGAN'

        total_processed = 0
        yosh_created = 0
        yosh_mahalla_updated = 0
        yosh_phone_updated = 0
        unemployed_created = 0
        unemployed_updated = 0
        errors = []

        with transaction.atomic():
            for row_idx in range(5, ws.max_row + 1):
                pinfl_raw = ws.cell(row=row_idx, column=4).value
                if not pinfl_raw:
                    continue
                jshshir = str(pinfl_raw).strip()
                if len(jshshir) < 10:
                    continue

                total_processed += 1
                fio = str(ws.cell(row=row_idx, column=6).value or '').strip()
                raw_mfy = ws.cell(row=row_idx, column=5).value
                mahalla = resolve_mahalla(row_idx, raw_mfy)

                if not mahalla:
                    errors.append(f"Qator {row_idx}: Mahalla topilmadi ({raw_mfy})")
                    continue

                phone_raw = ws.cell(row=row_idx, column=12).value
                phone = clean_phone(phone_raw)

                # Tug'ilgan sana
                b_date = ws.cell(row=row_idx, column=7).value
                if isinstance(b_date, datetime):
                    birth_date = b_date.date()
                elif isinstance(b_date, date):
                    birth_date = b_date
                else:
                    birth_date = None

                # Jinsi
                gender_raw = str(ws.cell(row=row_idx, column=8).value or '').strip()
                gender = 'Erkak' if gender_raw.lower() in ('erkak', 'эркак') else ('Ayol' if gender_raw.lower() in ('ayol', 'аёл') else '')

                category = get_category(ws.cell(row=row_idx, column=9).value, ws.cell(row=row_idx, column=10).value)
                direction = str(ws.cell(row=row_idx, column=10).value or '').strip()

                # 1. core.Yosh tekshirish / yaratish / yangilash
                yosh = Yosh.objects.filter(jshshir=jshshir).first()
                if not yosh:
                    if not birth_date:
                        # Fallback parsing from JSHSHIR if missing
                        try:
                            # 5/6 digit 2-7: DDMMYY
                            d = int(jshshir[1:3])
                            m = int(jshshir[3:5])
                            y_century = 2000 if jshshir[0] in ('5', '6') else 1900
                            y_year = y_century + int(jshshir[5:7])
                            birth_date = date(y_year, m, d)
                        except Exception:
                            birth_date = date(2005, 1, 1)

                    yosh = Yosh.objects.create(
                        fullname=fio,
                        jshshir=jshshir,
                        birth_date=birth_date,
                        mahalla=mahalla,
                        phone_number=phone,
                        address=mahalla.name,
                        school_gender=gender,
                    )
                    yosh_created += 1
                else:
                    save_needed = False
                    if yosh.mahalla_id != mahalla.id:
                        yosh.mahalla = mahalla
                        yosh_mahalla_updated += 1
                        save_needed = True

                    if phone and not yosh.phone_number:
                        yosh.phone_number = phone
                        yosh_phone_updated += 1
                        save_needed = True
                    elif phone and yosh.phone_number != phone:
                        yosh.phone_number = phone
                        yosh_phone_updated += 1
                        save_needed = True

                    if save_needed:
                        yosh.save()

                # 2. UnemployedYouth yaratish / yangilash (2026 II -> year=20262)
                # Foydalanuvchi ko'rsatmasi bo'yicha mas'ul rahbarlar e'tiborsiz qoldiriladi (leader=None)
                unemployed, was_created = UnemployedYouth.objects.update_or_create(
                    yosh=yosh,
                    defaults={
                        'year': 20262,
                        'category': category,
                        'direction': direction,
                        'leader': None,
                        'is_deleted': False,
                    }
                )
                if was_created:
                    unemployed_created += 1
                else:
                    unemployed_updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n=== IMPORT MUVAFFAQIYATLI YAKUNLANDI ===\n"
            f"Jami qayta ishlangan yoshlar: {total_processed}\n"
            f"Yangi yaratilgan Yoshlar (core_yosh): {yosh_created}\n"
            f"Mahallasi yangilangan Yoshlar: {yosh_mahalla_updated}\n"
            f"Telefoni kiritilgan/yangilangan Yoshlar: {yosh_phone_updated}\n"
            f"Yangi yaratilgan Ishsiz Yoshlar (2026 II): {unemployed_created}\n"
            f"Yangilangan Ishsiz Yoshlar (2026 II): {unemployed_updated}\n"
            f"Xatoliklar: {len(errors)}"
        ))
        if errors:
            for err in errors[:10]:
                self.stdout.write(self.style.WARNING(f"  {err}"))
