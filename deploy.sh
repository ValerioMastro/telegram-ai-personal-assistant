#!/usr/bin/env bash
set -Eeuo pipefail

# =========================
# Config
# =========================
SERVER_USER="opc"
SERVER_HOST="84.8.249.203"
SERVER_PATH="~/telegrambot/telegram-calendar-agent"
LOCAL_PATH="${HOME}/telegram-calendar-agent"

# Metti qui il path ESATTO della tua chiave SSH
SSH_KEY="${HOME}/Downloads/ssh-key-2026-03-13.key"

# =========================
# Checks
# =========================
if [[ ! -f "$SSH_KEY" ]]; then
  echo "❌ Chiave SSH non trovata: $SSH_KEY"
  exit 1
fi

if [[ ! -d "$LOCAL_PATH" ]]; then
  echo "❌ Cartella progetto non trovata: $LOCAL_PATH"
  exit 1
fi

echo "🚀 Deploy in corso..."
echo "📦 Local:  $LOCAL_PATH"
echo "🖥  Server: ${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}"
echo

# =========================
# Sync codice
# =========================
rsync -avz \
  --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.git' \
  --exclude '.DS_Store' \
  --exclude 'agent.db' \
  --exclude 'agent.db-shm' \
  --exclude 'agent.db-wal' \
  --exclude 'temp' \
  --exclude '*.log' \
  -e "ssh -i ${SSH_KEY}" \
  "${LOCAL_PATH}/" \
  "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/"

echo
echo "✅ Sync completato"
echo

# =========================
# Update server
# =========================
ssh -i "${SSH_KEY}" "${SERVER_USER}@${SERVER_HOST}" << 'EOF'
set -Eeuo pipefail

cd ~/telegrambot/telegram-calendar-agent

echo "📁 Cartella corrente:"
pwd

if [[ ! -d ".venv" ]]; then
  echo "⚠️ .venv non trovato, lo creo..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "⬆️ Aggiorno pip..."
python -m pip install --upgrade pip

echo "📚 Installo requirements..."
pip install -r requirements.txt

if [[ -f "agent.db" ]]; then
  echo "💾 Backup DB..."
  cp agent.db "agent.db.backup.$(date +%Y%m%d_%H%M%S)"
fi

echo "🔄 Riavvio servizio..."
sudo systemctl restart telegrambot

echo
echo "📊 Stato servizio:"
sudo systemctl status telegrambot --no-pager

echo
echo "🔎 Ultime righe log:"
journalctl -u telegrambot -n 20 --no-pager
EOF

echo
echo "🎉 Deploy completato"
echo "📌 Per vedere i log live:"
echo "ssh -i \"$SSH_KEY\" ${SERVER_USER}@${SERVER_HOST} 'journalctl -u telegrambot -f'"