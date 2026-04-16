#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

APP_DIR="${APP_DIR:-$PROJECT_DIR}"
CURRENT_LINK="${CURRENT_LINK:-/var/www/yoshlar/current}"
VENV_DIR="${VENV_DIR:-/var/www/yoshlar/venv}"
ENV_FILE="${ENV_FILE:-/var/www/yoshlar/shared/.env}"
SERVICE_NAME="${SERVICE_NAME:-yoshlar}"
BRANCH="${BRANCH:-main}"

if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "Git repo topilmadi: $APP_DIR"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env fayl topilmadi: $ENV_FILE"
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Python topilmadi: $VENV_DIR/bin/python"
  exit 1
fi

cd "$APP_DIR"

git fetch origin "$BRANCH"
git pull --ff-only origin "$BRANCH"

if [[ -L "$CURRENT_LINK" ]]; then
  ln -sfn "$APP_DIR" "$CURRENT_LINK"
fi

set -a
source "$ENV_FILE"
set +a

"$VENV_DIR/bin/python" -m pip install -r requirements.fresh.txt
"$VENV_DIR/bin/python" manage.py migrate --noinput
"$VENV_DIR/bin/python" manage.py collectstatic --noinput

if [[ $EUID -eq 0 ]]; then
  systemctl restart "$SERVICE_NAME"
else
  sudo systemctl restart "$SERVICE_NAME"
fi

if [[ $EUID -eq 0 ]]; then
  systemctl --no-pager --lines=20 status "$SERVICE_NAME"
else
  sudo systemctl --no-pager --lines=20 status "$SERVICE_NAME"
fi
