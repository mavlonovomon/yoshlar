# Yoshlar

Yoshlar bilan ishlash jarayonlarini yuritish uchun Django asosidagi ichki tizim.

Loyiha quyidagi yo'nalishlarni bitta panelda boshqaradi:

- yoshlar ro'yxati va profili
- maktab o'quvchilari qatlami
- mahallasi aniqlanmagan o'quvchilarni biriktirish oqimi
- ishsiz yoshlar bilan ishlash
- otaliq, migratsiya, reyd, besh tashabbus, yoqlama modullari
- intizom-jazo va kredit-yo'naltirish sahifalari
- bilim sinovi (test) moduli
- so'rovnoma moduli
- KPI hisoblash va mega-loyihalar statistikasi
- E-IMZO orqali autentifikatsiya endpointlari

## Joriy arxitektura

Bu loyiha hozir:

- Django 6.0.3
- SQLite 3 (`yoshlar.db`)
- Ubuntu serverda `gunicorn + systemd + Cloudflare Tunnel`

bilan ishlashga moslangan. Asosiy ma'lumotlar bazasi `yoshlar.db`.

## Texnologiyalar

- Python 3.14
- Django 6.0.3
- SQLite 3
- `gunicorn`
- `whitenoise`
- `pandas`, `openpyxl`
- `cryptography`

## Muhim eslatma

Loyiha asosiy baza sifatida bitta lokal SQLite faylidan foydalanadi.

- ma'lumotlar bazasi fayli: `yoshlar.db`
- fayl loyiha ildiz papkasida joylashadi
- boshqa DB ulanishlari ishlatilmaydi

## Tezkor ishga tushirish

### 1. Virtual muhit

```bash
python -m venv .venv
.venv\\Scripts\\Activate.ps1
```

### 2. Paketlar

```bash
pip install -r requirements.fresh.txt
```

### 3. `.env`

`.env.example` dan nusxa oling va quyidagilarni sozlang:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `MEDIA_ROOT`
- `STATIC_ROOT`

### 4. Migratsiya

```bash
python manage.py migrate
```

### 5. Tekshiruv

```bash
python manage.py check
```

### 6. Server

```bash
python manage.py runserver
```

Brauzerda:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/admin/`

## Production deploy

Ubuntu server uchun tavsiya etilgan oqim:

1. Repo'ni serverga clone qiling.
2. Git kodi `/home/genius/yoshlar/repo` ichida bo'lsin.
3. `/home/genius/yoshlar/current` ni `repo` ga ko'rsatadigan symlink qilib qo'ying.
4. `/home/genius/yoshlar/shared/.env` ni to'ldiring.
5. Virtualenv yarating va dependency'larni o'rnating.
6. `python manage.py migrate` ishga tushiring.
7. `python manage.py collectstatic --noinput` ishga tushiring.
8. `gunicorn` ni `systemd` service orqali ishga tushiring.
9. Cloudflare Tunnel ni `systemd` service orqali ulab qo'ying.
10. Yangilash uchun `git pull --ff-only` va `deploy/ubuntu/update.sh` oqimidan foydalaning.

Deploy uchun tayyor fayllar:

- [`deploy/ubuntu/README.md`](deploy/ubuntu/README.md)
- [`deploy/ubuntu/update.sh`](deploy/ubuntu/update.sh)
- [`deploy/ubuntu/bootstrap.sh`](deploy/ubuntu/bootstrap.sh)
- [`deploy/ubuntu/systemd/yoshlar.service`](deploy/ubuntu/systemd/yoshlar.service)
- [`deploy/ubuntu/systemd/cloudflared.service`](deploy/ubuntu/systemd/cloudflared.service)
- [`deploy/ubuntu/cloudflared/config.yml.example`](deploy/ubuntu/cloudflared/config.yml.example)

## Yangilash

GitHub'dan yangi commit kelganda serverda:

```bash
cd /home/genius/yoshlar/repo
bash deploy/ubuntu/update.sh
```

Bu skript:

- `git pull --ff-only`
- dependency yangilash
- migratsiya
- static fayllarni yig'ish
- `systemctl restart yoshlar`

`deploy/ubuntu/update.sh` serverdagi pull va restart oqimini bir joyga jamlaydi. Bu Windows'da yozib, Linux serverda `git pull` qilishni barqarorlashtirish uchun kerak.

## Muhim sozlamalar

`.env.example` ichidagi asosiy kalitlar:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `SESSION_COOKIE_SECURE`
- `CSRF_COOKIE_SECURE`
- `MEDIA_ROOT`
- `STATIC_ROOT`
- `GUNICORN_BIND`
- `GUNICORN_WORKERS`
- `GUNICORN_TIMEOUT`

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

Maktab o'quvchilari importi:

```bash
python manage.py import_maktab_oquvchilar_from_rp --file "C:\\Users\\Genius007\\Desktop\\RP.xlsx"
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
- `Yosh.school_*` maydonlari orqali maktab o'quvchilari qatlami
- `Yosh.age_years` orqali yosh ustuni
- `MaktabOquvchi` staging qatlami orqali mahallasi aniqlanmagan o'quvchilar oqimi
- `sorovnoma`
- `auth` (E-IMZO)

## Git bo'yicha eslatma

Repo uchun quyidagi qoidalar qo'llanadi:

- `.gitattributes` orqali line ending nazorat qilinadi
- `.editorconfig` bilan LF/CRLF siyosati belgilanadi
- dump, backup va database fayllar repoga qo'shilmaydi

Bu Windows'da yozib, Linux serverda `git pull` qilishni barqarorlashtiradi.
