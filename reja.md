# Yetakchi KPI bo'yicha reja (mavjud ma'lumotlar asosida)

## 1) Maqsad
Mavjud tizimdagi real ma'lumotlardan foydalanib, har bir yetakchi uchun o'lchanadigan, adolatli va avtomatlashtirilgan KPI tizimini yaratish.

## 2) Mavjud data manbalari (hozir tizimda bor)
- `core.Yosh`, `core.Uchrashuv`: umumiy yoshlar bazasi va suhbatlar.
- `ishsiz_yoshlar.UnemployedYouth`, `YouthMeeting`, `AssistanceInfo`: ishsiz yoshlar, uchrashuvlar, 5 yo'nalish bo'yicha yordam.
- `migratsiya.MigrationYouth`, `MigrationMeeting`: migratsiyadagi yoshlar va monitoring suhbatlari.
- `otaliq.OtaliqYouth`, `OtaliqMeeting`, `OtaliqAssistance`: risk toifasidagi yoshlar bilan ish.
- `yoqlama.AttendanceSession`, `AttendanceRecord`: intizom/qatnashuv ko'rsatkichlari.
- `ishsiz_yoshlar.Task`, `TaskResponse`, `TaskNotification`: topshiriq ijrosi va muddat.
- `core.*StatSnapshot` (Mutolaa/UstozAI/UzChess/Qizlar): mega loyihalar bo'yicha mahalla kesimidagi natijalar.

## 3) KPI strukturasi (taklif)
KPI 100 ballik tizimda, 5 blok:

1. Qamrov va faollik (25 ball)
- Yoshlar bazasida biriktirilgan yoshlar bilan ish faolligi.
- Formula: `suhbat_bor / jami_yosh`.

2. Ijtimoiy natija (30 ball)
- Ishsiz yoshlar bo'yicha bandlik natijalari.
- Formula: `yordam_olgan / ishsiz_jami`.
- 5 yo'nalish alohida sub-metrika: ish, kredit, migratsiya, yer, asbob-uskuna.

3. Xavf guruhlari bilan ish sifati (20 ball)
- Otaliq + Migratsiya segmentlarida uchrashuv qamrovi va yangiligi.
- Formula: `oxirgi_30_kun monitoring qamrovi`.

4. Intizom va topshiriq ijrosi (15 ball)
- Yo'qlama statuslari + task completion.
- Formula: `yakunlangan_task / jami_task`, kechikkanlar uchun penalti.

5. Mega loyihalar natijadorligi (10 ball)
- Mahalla bo'yicha mavjud mega snapshot ko'rsatkichlari normalizatsiya qilinadi.

## 4) KPI hisoblash qoidalari
- Har bir metrika 0..100 ga normalizatsiya qilinadi.
- So'ngra vazn bo'yicha yig'iladi:
  - 25 + 30 + 20 + 15 + 10 = 100.
- Ma'lumot yetishmasa:
  - `null` emas, "N/A" status.
  - Yakuniy KPI’da penalti emas, "coverage warning" chiqarish.

## 5) Liderbord va kesimlar
- Kesimlar:
  - Mahalla bo'yicha.
  - Sektor bo'yicha.
  - Tuman bo'yicha umumiy.
- Davr:
  - Haftalik.
  - Oylik (asosiy KPI).
  - Choraklik trend.

## 6) Texnik implementatsiya rejasi
1. KPI modeli qo'shish:
- `LeaderKpiSnapshot` (date_from, date_to, user, block_scores, total_score, debug_json).

2. Hisoblash servisi:
- `core/services/kpi_service.py`:
  - `compute_leader_kpi(user, from_date, to_date)`.
  - Har blok uchun alohida funksiya.

3. Batch command:
- `python manage.py compute_kpi --month=YYYY-MM`.
- Oylik snapshot saqlash.

4. UI:
- KPI Dashboard (top cards + ranking table + trend chart).
- Leader detail KPI (blocklar kesimida breakdown).

5. Audit:
- Har KPI qatorida "drill-down" link:
  - qaysi yozuvlar score berganini ko'rsatish.

## 7) Data sifati bo'yicha muhim nuqtalar
- `assistance_type` faqat 5 yo'nalishda qolishi kerak (hozir moslashtirildi).
- `meeting_date`, `date_provided`, `task.due_date` bo'sh bo'lmasligi kerak.
- Mahalla mapping bir xil bo'lishi shart (`Yosh.mahalla`, leader biriktirishlar).

## 8) KPI v1 (tez ishga tushirish) scope
- Faqat quyidagilar bilan boshlash:
  - Umumiy suhbat qamrovi.
  - Ishsizlar bandlik foizi.
  - Topshiriq ijrosi.
  - Yo'qlama intizomi.
- Mega loyihalar KPI’sini v1.1 ga qoldirish mumkin.

## 9) KPI v2 (kengaytma)
- Risk-adjusted KPI:
  - og'ir toifalardagi yoshlar uchun koeffitsiyent.
- Time-decay:
  - eski faoliyatga kamroq ball, yangi natijaga ko'proq ball.
- Prediction:
  - kelgusi oy "xavfli mahallalar" prognozi.

## 10) Keyingi amaliy qadamlar
1. KPI model va migration yaratish.
2. `kpi_service` skeleton yozish.
3. 1 oylik test hisoblashni localda chiqarish.
4. UI prototip (`/kpi/`) ochish.
5. Formula vaznlarini rahbariyat bilan tasdiqlash.
