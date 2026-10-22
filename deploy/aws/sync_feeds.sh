#!/usr/bin/env bash
# Pull raw feeds from the S3 landing bucket into the workspace and ingest them. Run on the EC2 host (instance role)
# or locally with credentials. usage: ./sync_feeds.sh <source> <feed> <mapping.yaml> [full|incremental]
. "$(dirname "$0")/common.sh"; require RAW_BUCKET
SRC="${1:?source}"; FEED="${2:?feed}"; MAP="${3:?mapping yaml}"; MODE="${4:-incremental}"
DEST="${AURORA_WORKSPACE:-.aurora}/landing/$SRC/$FEED"; mkdir -p "$DEST"
aws_ s3 sync "s3://$RAW_BUCKET/raw/$SRC/$FEED/" "$DEST/" --exact-timestamps
for f in "$DEST"/**/*.csv "$DEST"/*.csv; do [ -f "$f" ] || continue; aurora ingest "$f" -s "$SRC" -f "$FEED" --mode "$MODE" -m "$MAP"; done
