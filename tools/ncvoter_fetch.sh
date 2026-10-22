#!/usr/bin/env bash
# Download NC voter-registration snapshots and convert them from UTF-16LE to UTF-8 TSV.
#   tools/ncvoter_fetch.sh <out-dir> 20230101 20240101 20250101
set -euo pipefail
OUT="${1:?out dir}"; shift
mkdir -p "$OUT"
for d in "$@"; do
  z="$OUT/VR_Snapshot_$d.zip"; t="$OUT/VR_Snapshot_$d.tsv"
  [ -s "$t" ] && { echo "have $t"; continue; }
  [ -s "$z" ] || curl -fL --retry 3 -o "$z" "https://s3.amazonaws.com/dl.ncsbe.gov/data/Snapshots/VR_Snapshot_$d.zip"
  unzip -p "$z" "VR_Snapshot_$d.txt" | iconv -f UTF-16LE -t UTF-8 -c | tr -d '\r' > "$t"
  echo "$t: $(wc -l < "$t") lines"; rm -f "$z"
done
