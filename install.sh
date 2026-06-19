#!/bin/bash
# Install the persistent boot-time PL1=10W applier (Jumper EZbook N3450).
# Run with sudo.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
install -m 0755 "$HERE/scripts/ezbook-pl1.py" /usr/local/sbin/ezbook-pl1.py
install -m 0644 "$HERE/systemd/ezbook-power-limit.service" /etc/systemd/system/ezbook-power-limit.service
systemctl daemon-reload
systemctl enable --now ezbook-power-limit.service
systemctl --no-pager status ezbook-power-limit.service | head -n 12
echo
echo "Installed. PL1 will be set to 10W on every boot (CPU-only benefit; see README)."
