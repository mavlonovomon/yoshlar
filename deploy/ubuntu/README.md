# Ubuntu deploy

Bu loyiha Ubuntu serverda `gunicorn + systemd + Cloudflare Tunnel` bilan ishlashi uchun tayyorlangan.

Serverdagi tavsiya etilgan tuzilma:

- `/home/genius/yoshlar/repo` - Git'dan keladigan kod
- `/home/genius/yoshlar/current` - `repo` ga ko'rsatadigan symlink
- `/home/genius/yoshlar/shared` - muqim fayllar: `.env`, `db`, `media`, `staticfiles`, `logs`
- `/home/genius/yoshlar/venv` - virtual muhit

## Bir martalik o'rnatish

1. Kerakli paketlarni o'rnating:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

2. Repo'ni serverga clone qiling:

```bash
mkdir -p /home/genius/yoshlar
git clone https://github.com/mavlonovomon/yoshlar.git /home/genius/yoshlar/repo
ln -sfn /home/genius/yoshlar/repo /home/genius/yoshlar/current
```

3. Bootstrap skriptini ishga tushiring:

```bash
cd /home/genius/yoshlar/repo
bash deploy/ubuntu/bootstrap.sh
```

4. `/home/genius/yoshlar/shared/.env` faylini to'ldiring:

- `ALLOWED_HOSTS=example.com,www.example.com`
- `CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com`
- `SQLITE_PATH=/home/genius/yoshlar/shared/db/yoshlar.db`
- `MEDIA_ROOT=/home/genius/yoshlar/shared/media`
- `STATIC_ROOT=/home/genius/yoshlar/shared/staticfiles`

Ma'lumotlar bazasi endi alohida servisga ulanmaydi:

- Django `SQLITE_PATH` orqali `/home/genius/yoshlar/shared/db/yoshlar.db` faylidan foydalanadi
- serverda `shared/db` papkasiga yozish huquqi bo'lishi kerak

5. Systemd unitlarni joylang:

```bash
sudo cp deploy/ubuntu/systemd/yoshlar.service /etc/systemd/system/yoshlar.service
sudo cp deploy/ubuntu/systemd/cloudflared.service /etc/systemd/system/cloudflared.service
sudo mkdir -p /etc/cloudflared
sudo cp deploy/ubuntu/cloudflared/config.yml.example /etc/cloudflared/config.yml
```

6. Service'larni yoqing:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now yoshlar
sudo systemctl enable --now cloudflared
```

## Yangilash

Repo'ga yangi commit push qilingandan keyin serverda:

```bash
cd /home/genius/yoshlar/repo
bash deploy/ubuntu/update.sh
```

Bu skript:

- `git pull --ff-only`
- dependency yangilash
- `migrate`
- `collectstatic`
- `systemctl restart yoshlar`

## Eslatma

`cloudflared` ichki trafikni `http://127.0.0.1:8000` ga yuboradi, shuning uchun Django'da:

- `SECURE_PROXY_SSL_HEADER`
- `CSRF_TRUSTED_ORIGINS`
- `USE_X_FORWARDED_HOST`

to'g'ri sozlangan bo'lishi kerak.
