#!/usr/bin/env bash
# Shared helpers. Scripts are idempotent where the AWS API allows and never delete resources unless called via destroy.sh.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$HERE/.env" ]; then set -a; . "$HERE/.env"; set +a; else echo "missing $HERE/.env (copy env.example)"; exit 1; fi
export AWS_PROFILE AWS_REGION
aws_() { aws --region "$AWS_REGION" --output text "$@"; }
require() { for v in "$@"; do [ -n "${!v:-}" ] || { echo "env $v is required"; exit 1; }; done; }
tag_args() { echo "Key=Project,Value=$PROJECT Key=Env,Value=$ENV_NAME"; }
log() { printf '\033[1;34m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
