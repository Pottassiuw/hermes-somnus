#!/usr/bin/env bash
# Hermes Phase 2 Host Provisioning Script (Run with sudo on the host)
set -euo pipefail

echo "=== [1/5] Creating Host Users ==="
id hermes-control &>/dev/null || useradd -r -s /usr/sbin/nologin -d /var/empty hermes-control
id hermes-publish &>/dev/null || useradd -r -s /usr/sbin/nologin -d /var/empty hermes-publish

echo "=== [2/5] Creating Directories ==="
mkdir -p /etc/hermes/ssh /etc/hermes/profile /etc/hermes/checks
mkdir -p /srv/hermes/jobs /srv/hermes/receipts/current /srv/hermes/verify/repo
mkdir -p /usr/local/libexec

echo "=== [3/5] Installing Executables ==="
install -m 0755 bin/hermes-enter.sh /usr/local/libexec/hermes-enter.sh
install -m 0755 bin/smoke_gate.py /usr/local/libexec/smoke_gate.py
install -m 0755 bin/run-one /usr/local/libexec/run-one
install -m 0755 bin/publish /usr/local/libexec/publish

echo "=== [4/5] Installing Configuration and Policies ==="
install -m 0644 ops/authority.json /etc/hermes/authority.json
install -m 0644 ops/images.lock /etc/hermes/images.lock
install -m 0644 ops/profile/config.yaml /etc/hermes/profile/config.yaml

echo "=== [5/5] Installing Systemd Units ==="
install -m 0644 ops/systemd/hermes-task.service /etc/systemd/system/hermes-task.service
install -m 0644 ops/systemd/hermes-task.timer /etc/systemd/system/hermes-task.timer
systemctl daemon-reload

echo "=== Installation complete ==="
