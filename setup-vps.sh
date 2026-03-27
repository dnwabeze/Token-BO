#!/bin/bash
# Run this on your Hostinger VPS after cloning the repo
# Usage: bash setup-vps.sh

set -e

echo "=== Installing system dependencies ==="
apt update && apt install -y python3.11 python3.11-venv python3-pip git

echo "=== Creating virtual environment ==="
cd /root/trend-bot
python3.11 -m venv venv

echo "=== Installing Python dependencies ==="
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

echo "=== Creating data directory ==="
mkdir -p data

echo "=== Setting up systemd service ==="
cp trend-bot.service /etc/systemd/system/trend-bot.service
systemctl daemon-reload
systemctl enable trend-bot

echo ""
echo "=== DONE ==="
echo ""
echo "Next steps:"
echo "  1. Create your .env file:  nano /root/trend-bot/.env"
echo "  2. Paste your credentials from .env.example"
echo "  3. Start the bot:  systemctl start trend-bot"
echo "  4. Check logs:     journalctl -u trend-bot -f"
