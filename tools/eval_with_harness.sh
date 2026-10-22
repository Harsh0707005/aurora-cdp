#!/usr/bin/env bash
# Run the aurora-eval-harness evaluation of THIS engine from the aurora-cdp repo root.
#
#   tools/eval_with_harness.sh <tier|dataset-path> [run-name] [extra aurora-eval run flags...]
#
# Examples (from ~/Desktop/Projects/aurora-cdp):
#   tools/eval_with_harness.sh small
#   tools/eval_with_harness.sh medium medium --isolate-windows
#   EVAL_SEED=20261022 DATE=2026-10-22 tools/eval_with_harness.sh large large --isolate-windows --timeout-s 7200
#
# The whole harness invocation is wrapped in `/usr/bin/time -l` (macOS) so the kernel's "maximum resident set
# size" of the process tree is captured without any extra dependency; it is parsed into
# $AURORA_DATA_DIR/eval-runs/<run-name>.time.json next to the harness's own psutil/getrusage figures.
# Reports land in reports/<DATE>/<run-name>/ in this repo (report.md, metrics.json, provenance.json, plots/).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HARNESS="${AURORA_EVAL_HARNESS:-$HERE/../aurora-eval-harness}"
export AURORA_DATA_DIR="${AURORA_DATA_DIR:-$HOME/Documents/aanya/datasets/aurora-testdata}"
mkdir -p "$AURORA_DATA_DIR/eval-runs"
PY="$HARNESS/.venv/bin/python"
[ -x "$PY" ] || { echo "harness venv not found at $PY (see $HARNESS/README.md)"; exit 2; }
DATASET="${1:?tier or dataset path}"; shift || true
RUN_NAME="${1:-$(basename "$DATASET")}"; [ $# -gt 0 ] && shift
SEED="${EVAL_SEED:-20261022}"
DATE="${DATE:-$(date +%F)}"
TIMELOG="$AURORA_DATA_DIR/eval-runs/$RUN_NAME.time.txt"
START="$(date -u +%FT%TZ)"
set +e
( cd "$HARNESS" && /usr/bin/time -l "$PY" -m aurora_eval.cli run --adapter aurora_cdp --dataset "$DATASET" \
    --seed "$SEED" --run-name "$RUN_NAME" --date "$DATE" --reports-root "$HERE/reports" "$@" ) 2> >(tee "$TIMELOG" >&2)
STATUS=$?
set -e
END="$(date -u +%FT%TZ)"
# parse `/usr/bin/time -l` (bytes on macOS) into JSON next to the run
"$PY" - "$TIMELOG" "$RUN_NAME" "$START" "$END" "$STATUS" <<'PYEOF'
import json, re, sys, os
log, run, start, end, status = sys.argv[1:6]
txt = open(log, errors="replace").read()
def grab(pat, cast=float):
    m = re.search(pat, txt)
    return cast(m.group(1)) if m else None
out = {"run_name": run, "start": start, "end": end, "exit_status": int(status),
       "wall_s": grab(r"([\d.]+) real"), "user_s": grab(r"([\d.]+) user"), "sys_s": grab(r"([\d.]+) sys"),
       "max_rss_mb": (lambda b: round(b / 1048576, 1) if b else None)(grab(r"(\d+)\s+maximum resident set size", int)),
       "source": "/usr/bin/time -l"}
path = os.path.join(os.environ["AURORA_DATA_DIR"], "eval-runs", f"{run}.time.json")
json.dump(out, open(path, "w"), indent=2)
print(json.dumps(out))
PYEOF
exit $STATUS
