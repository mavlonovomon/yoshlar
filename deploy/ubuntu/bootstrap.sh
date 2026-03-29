#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/mavlonovomon/yoshlar.git}"
APP_ROOT="${APP_ROOT:-/home/genius/yoshlar}"
REPO_DIR="${REPO_DIR:-$APP_ROOT/repo}"
CURRENT_LINK="${CURRENT_LINK:-$APP_ROOT/current}"
VENV_DIR="${VENV_DIR:-$APP_ROOT/venv}"
SHARED_DIR="${SHARED_DIR:-$APP_ROOT/shared}"
ENV_FILE="${ENV_FILE:-$SHARED_DIR/.env}"

mkdir -p "$APP_ROOT" "$VENV_DIR" "$SHARED_DIR/media" "$SHARED_DIR/staticfiles" "$SHARED_DIR/db" "$SHARED_DIR/logs"

if [[ ! -d "$REPO_DIR/.git" ]]; then
  git clone "$REPO_URL" "$REPO_DIR"
fi

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$REPO_DIR/requirements.fresh.txt"

ln -sfn "$REPO_DIR" "$CURRENT_LINK"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$REPO_DIR/.env.example" "$ENV_FILE"
  echo "Env fayl yaratildi: $ENV_FILE"
fi

echo "Keyingi qadamlar:"
echo "1. $ENV_FILE ni tahrir qiling"
echo "2. SQLITE_PATH=$SHARED_DIR/db/yoshlar.db qiymatini tekshiring"
echo "3. sudo cp $REPO_DIR/deploy/ubuntu/systemd/yoshlar.service /etc/systemd/system/yoshlar.service"
echo "4. sudo cp $REPO_DIR/deploy/ubuntu/systemd/cloudflared.service /etc/systemd/system/cloudflared.service"
echo "5. sudo systemctl daemon-reload"
echo "6. sudo systemctl enable --now yoshlar cloudflared"
