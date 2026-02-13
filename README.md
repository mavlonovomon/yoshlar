# Yoshlar

Yoshlar bilan ishlash jarayonlarini yuritish uchun Django asosidagi ichki tizim.
Loyiha bir nechta yo'nalishlarni bitta panelda boshqaradi:

- yoshlar ro'yxati va profili
- ishsiz yoshlar bilan ishlash
- otaliq, migratsiya, reyd, besh tashabbus, yoqlama modullari
- intizom-jazo va kredit-yo'naltirish sahifalari
- bilim sinovi (test) moduli
- KPI hisoblash va mega-loyihalar statistikasi (Mutolaa, Ustoz AI, UzChess, Qizlar akademiyasi)
- E-IMZO orqali autentifikatsiya endpointlari

## Texnologiyalar

- Python 3.13 (loyihadagi `.pyc` fayllariga ko'ra)
- Django 6.x (migratsiya fayllari bo'yicha)
- SQLite (`yoshlar.db`)
- Qo'shimcha kutubxonalar:
  - `cryptography` (E-IMZO verifikatsiya uchun)
  - `pandas`, `openpyxl` (Excel import skriptlari uchun)

## Tezkor ishga tushirish (local)

1. Loyihani clone qiling:

```bash
git clone https://github.com/mavlonovomon/yoshlar.git
cd yoshlar
```

2. Virtual environment yarating va yoqing:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

3. Kerakli paketlarni o'rnating:

```bash
pip install django cryptography pandas openpyxl
```

4. `.env` fayl yarating:

```bash
copy .env.example .env
```

5. Migratsiyalarni ishga tushiring:

```bash
python manage.py migrate
```

6. Admin foydalanuvchi yarating:

```bash
python setup_admin.py
```

7. Serverni ishga tushiring:

```bash
python manage.py runserver
```

8. Brauzerda oching:

- `http://127.0.0.1:8000/login/`
- `http://127.0.0.1:8000/admin/`

## Muhim sozlamalar (.env)

`.env.example` ichidagi asosiy kalitlar:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `DATABASE_URL`
- `ADMIN_PASSWORD`
- `MUTOLAA_STATS_URL`
- `USTOZ_AI_STATS_URL`
- `UZCHESS_STATS_URL`
- `QIZLAR_STATS_URL`
- `EMAIL_BACKEND`

## Management commandlar

Mega-loyihalar statistikasi:

```bash
python manage.py fetch_mutolaa_stats
python manage.py fetch_ustoz_ai_stats
python manage.py fetch_uzchess_stats
python manage.py fetch_qizlar_stats
```

Alias mapping seed commandlari:

```bash
python manage.py seed_uzchess_aliases
python manage.py seed_qizlar_aliases
```

KPI hisoblash:

```bash
python manage.py compute_kpi
python manage.py compute_kpi --month 2026-02
python manage.py compute_kpi --from-date 2026-02-01 --to-date 2026-02-13
python manage.py compute_kpi --dry-run
```

## E-IMZO

`certs/` papkaga CA bundle joylashtiring:

- fayl: `certs/eimzo_ca_bundle.pem`
- izoh: `certs/README.txt`

Auth endpointlar:

- `GET /auth/eimzo/`
- `POST /auth/eimzo/challenge/`
- `POST /auth/eimzo/verify/`

## Loyiha tuzilmasi

Asosiy app'lar:

- `core`
- `ishsiz_yoshlar`
- `otaliq`
- `migratsiya`
- `reyd`
- `beshtashabbus`
- `yoqlama`
- `profilaktika`
- `kredit_yo_naltirish`
- `intizom_jazo`
- `bilim_sinovi`
- `auth` (E-IMZO)

## Git bo'yicha eslatma

Quyidagilar `.gitignore` orqali repoga qo'shilmaydi:

- `yoshlar.db`
- `media/`
- `staticfiles/`
- `.env`

Bu fayllar local muhit va foydalanuvchi ma'lumotlariga bog'liq bo'lgani uchun repository'da saqlanmaydi.
