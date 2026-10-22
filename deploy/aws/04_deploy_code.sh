#!/usr/bin/env bash
# Upload the repo (tracked files only) to the EC2 host and (re)start the compose stack.
# usage: ./04_deploy_code.sh <public-ip> [path/to/key.pem]
. "$(dirname "$0")/common.sh"
IP="${1:?public ip}"; KEY="${2:-$HOME/.ssh/$EC2_KEY_NAME.pem}"
ROOT="$(cd "$HERE/../.." && pwd)"
TAR=$(mktemp -t aurora-cdp.XXXX.tgz)
( cd "$ROOT" && git ls-files -z aurora_cdp docker pyproject.toml README.md | tar --null -czf "$TAR" -T - )
log "uploading $(du -h "$TAR" | cut -f1) to ec2-user@$IP"
scp -o StrictHostKeyChecking=accept-new -i "$KEY" "$TAR" "ec2-user@$IP:/tmp/aurora-cdp.tgz"
ssh -i "$KEY" "ec2-user@$IP" bash -s <<EOS
set -euo pipefail
cd /opt/aurora-cdp && tar -xzf /tmp/aurora-cdp.tgz
cat > .env <<ENV
POSTGRES_PASSWORD=${RDS_PASSWORD}
AURORA_PEOPLE=700
AURORA_INTERVAL=900
ENV
sudo systemctl restart aurora-cdp.service
sleep 5; curl -fsS http://localhost:8000/health || (docker compose -f docker/docker-compose.yml logs --tail=50 api; exit 1)
EOS
rm -f "$TAR"
log "deployed: http://$IP:8000/ui"
