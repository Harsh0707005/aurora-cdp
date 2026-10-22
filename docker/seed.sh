#!/usr/bin/env bash
# Seed the shared volume with demo data and a complete pipeline run (idempotent: skips if a DB already exists).
set -euo pipefail
WS="${AURORA_WORKSPACE:-/data/aurora}"
OUT="${AURORA_OUTPUTS:-/data/outputs}"
PEOPLE="${AURORA_PEOPLE:-700}"
mkdir -p "$WS" "$OUT"
cd "$OUT"
if [ -f "$WS/aurora.duckdb" ] && [ "${AURORA_RESEED:-0}" != "1" ]; then
  echo "seed: $WS/aurora.duckdb exists, skipping (set AURORA_RESEED=1 to regenerate)"
  exit 0
fi
echo "seed: generating demo data for $PEOPLE people into $WS"
aurora demo --people "$PEOPLE" --workspace "$WS"
aurora report --workspace "$WS"
aurora stitch export --workspace "$WS" --out "$OUT/assignments.csv" --scores-out "$OUT/scores.csv"
echo "seed: done -> db $WS/aurora.duckdb ; outputs $OUT"
