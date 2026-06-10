#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

INSTALL_DIR="${INSTALL_DIR:-/opt/trading-agent-ops}"
APP_USER="${APP_USER:-${SUDO_USER:-$(id -un)}}"
APP_GROUP="${APP_GROUP:-$(id -gn "${APP_USER}" 2>/dev/null || echo "${APP_USER}")}"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
DOMAIN="${DOMAIN:-_}"
ADAPTER="${ADAPTER:-mock}"
TICK_INTERVAL="${TICK_INTERVAL:-2.2}"
TUSHARE_TOKEN="${TUSHARE_TOKEN:-}"
DB_PATH="${DB_PATH:-market.db}"
SERVICE_NAME="${SERVICE_NAME:-market-terminal-api}"
NGINX_CONF="${NGINX_CONF:-/etc/nginx/conf.d/market-terminal.conf}"
SKIP_NGINX="${SKIP_NGINX:-0}"
SKIP_SYSTEMD="${SKIP_SYSTEMD:-0}"
SKIP_HEALTHCHECK="${SKIP_HEALTHCHECK:-0}"

BACKEND_SRC="${REPO_ROOT}/market-api"
FRONTEND_SRC="${REPO_ROOT}/market-terminal"
BACKEND_DIR="${INSTALL_DIR}/market-api"
FRONTEND_DIR="${INSTALL_DIR}/market-terminal"
FRONTEND_DIST="${FRONTEND_DIR}/dist"

log() {
  printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

run_as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

run_as_user() {
  if [[ "$(id -un)" == "${APP_USER}" ]]; then
    "$@"
  elif [[ "$(id -u)" -eq 0 ]]; then
    sudo -u "${APP_USER}" -- "$@"
  else
    sudo -u "${APP_USER}" -- "$@"
  fi
}

write_file_as_root() {
  local target="$1"
  local tmp
  tmp="$(mktemp)"
  cat >"${tmp}"
  run_as_root install -m 0644 "${tmp}" "${target}"
  rm -f "${tmp}"
}

log "Checking prerequisites"
need_cmd python3
need_cmd npm
need_cmd rsync
need_cmd curl

if [[ ! -d "${BACKEND_SRC}" || ! -d "${FRONTEND_SRC}" ]]; then
  echo "Run this script from the repository checkout. Missing market-api or market-terminal." >&2
  exit 1
fi

log "Creating install directories under ${INSTALL_DIR}"
run_as_root mkdir -p "${BACKEND_DIR}" "${FRONTEND_DIST}"

log "Building frontend"
cd "${FRONTEND_SRC}"
if [[ -f package-lock.json ]]; then
  run_as_user npm ci
else
  run_as_user npm install
fi
run_as_user npm run build

log "Syncing frontend dist to ${FRONTEND_DIST}"
run_as_root rsync -a --delete "${FRONTEND_SRC}/dist/" "${FRONTEND_DIST}/"

log "Syncing backend source to ${BACKEND_DIR}"
run_as_root rsync -a --delete \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude 'market.db' \
  "${BACKEND_SRC}/" "${BACKEND_DIR}/"

log "Setting ownership for ${INSTALL_DIR}"
run_as_root chown -R "${APP_USER}:${APP_GROUP}" "${INSTALL_DIR}"

log "Installing backend dependencies"
cd "${BACKEND_DIR}"
if [[ ! -d .venv ]]; then
  run_as_user python3 -m venv .venv
fi
run_as_user "${BACKEND_DIR}/.venv/bin/python" -m pip install --upgrade pip
run_as_user "${BACKEND_DIR}/.venv/bin/pip" install -r requirements.txt

if [[ ! -f "${BACKEND_DIR}/.env" ]]; then
  log "Creating backend .env"
  write_file_as_root "${BACKEND_DIR}/.env" <<EOF
ADAPTER=${ADAPTER}
TICK_INTERVAL=${TICK_INTERVAL}
TUSHARE_TOKEN=${TUSHARE_TOKEN}
DB_PATH=${DB_PATH}
EOF
  run_as_root chown "${APP_USER}:${APP_GROUP}" "${BACKEND_DIR}/.env"
else
  log "Keeping existing backend .env"
fi

if [[ "${SKIP_SYSTEMD}" != "1" ]]; then
  log "Writing systemd service ${SERVICE_NAME}"
  write_file_as_root "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Market Terminal API
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${BACKEND_DIR}
ExecStart=${BACKEND_DIR}/.venv/bin/uvicorn main:app --host ${API_HOST} --port ${API_PORT}
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
  run_as_root systemctl daemon-reload
  run_as_root systemctl enable "${SERVICE_NAME}"
  run_as_root systemctl restart "${SERVICE_NAME}"
else
  log "Skipping systemd setup because SKIP_SYSTEMD=1"
fi

if [[ "${SKIP_NGINX}" != "1" ]]; then
  need_cmd nginx
  log "Writing Nginx config ${NGINX_CONF}"
  write_file_as_root "${NGINX_CONF}" <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    root ${FRONTEND_DIST};
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://${API_HOST}:${API_PORT};
        proxy_http_version 1.1;

        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Connection "";

        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        add_header X-Accel-Buffering no;
    }

    location /health {
        proxy_pass http://${API_HOST}:${API_PORT}/health;
        proxy_set_header Host \$host;
    }
}
EOF
  run_as_root nginx -t
  run_as_root systemctl reload nginx
else
  log "Skipping Nginx setup because SKIP_NGINX=1"
fi

if [[ "${SKIP_HEALTHCHECK}" == "1" ]]; then
  log "Skipping health check because SKIP_HEALTHCHECK=1"
else
  log "Running health check"
  if curl -fsS "http://${API_HOST}:${API_PORT}/health" >/dev/null; then
    log "Backend health check passed"
  else
    log "Backend health check failed. Check: journalctl -u ${SERVICE_NAME} -n 100"
    exit 1
  fi
fi

cat <<EOF

Deploy complete.

Frontend:
  ${FRONTEND_DIST}

Backend:
  ${BACKEND_DIR}
  http://${API_HOST}:${API_PORT}/health

Systemd:
  ${SERVICE_NAME}

Nginx:
  ${NGINX_CONF}

Open:
  http://${DOMAIN}/

EOF
