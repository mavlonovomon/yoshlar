#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/mavlonovomon/yoshlar.git}"
APP_DIR="${APP_DIR:-/var/www/yoshlar/current}"
VENV_DIR="${VENV_DIR:-/var/www/yoshlar/venv}"
SHARED_DIR="${SHARED_DIR:-/var/www/yoshlar/shared}"
ENV_FILE="${ENV_FILE:-$SHARED_DIR/.env}"

mkdir -p "$APP_DIR" "$VENV_DIR" "$SHARED_DIR/media" "$SHARED_DIR/staticfiles" "$SHARED_DIR/db" "$SHARED_DIR/logs"

if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone "$REPO_URL" "$APP_DIR"
fi

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$APP_DIR/requirements.fresh.txt"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$APP_DIR/.env.example" "$ENV_FILE"
  echo "Env fayl yaratildi: $ENV_FILE"
fi

echo "Keyingi qadamlar:"
echo "1. $ENV_FILE ni tahrir qiling"
echo "2. sudo cp $APP_DIR/deploy/ubuntu/systemd/yoshlar.service /etc/systemd/system/yoshlar.service"
echo "3. sudo cp $APP_DIR/deploy/ubuntu/systemd/cloudflared.service /etc/systemd/system/cloudflared.service"
echo "4. sudo systemctl daemon-reload"
echo "5. sudo systemctl enable --now yoshlar cloudflared"
