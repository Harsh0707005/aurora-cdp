#!/bin/bash
# EC2 user-data: docker + compose plugin, data dir, systemd unit for the compose stack (code arrives via 04_deploy_code.sh).
set -euxo pipefail
dnf update -y && dnf install -y docker git
systemctl enable --now docker
usermod -aG docker ec2-user
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
mkdir -p /opt/aurora-cdp /data/aurora && chown -R ec2-user:ec2-user /opt/aurora-cdp /data
cat >/etc/systemd/system/aurora-cdp.service <<'UNIT'
[Unit]
Description=Aurora CDP compose stack
After=docker.service
Requires=docker.service
[Service]
Type=oneshot
RemainAfterExit=true
WorkingDirectory=/opt/aurora-cdp
EnvironmentFile=-/opt/aurora-cdp/.env
ExecStart=/usr/bin/docker compose -f docker/docker-compose.yml up -d --build
ExecStop=/usr/bin/docker compose -f docker/docker-compose.yml down
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload && systemctl enable aurora-cdp.service
