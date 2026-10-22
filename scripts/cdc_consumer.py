"""Demo CDC consumer: tail data/cdc/*.jsonl and print events as they arrive.

Usage: python scripts/cdc_consumer.py [--root data/cdc] [--follow]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data/cdc")
    ap.add_argument("--follow", action="store_true", help="keep polling for new files/lines")
    args = ap.parse_args()
    root = Path(args.root)
    offsets: dict[Path, int] = {}
    while True:
        for f in sorted(root.glob("*.jsonl")):
            pos = offsets.get(f, 0)
            with open(f) as fh:
                fh.seek(pos)
                for line in fh:
                    ev = json.loads(line)
                    who = f"{ev.get('datasource')}/{ev.get('pk')}" if ev.get("pk") else ""
                    print(f"{ev['ts']} {ev['type']:<18} {ev.get('previous_id') or '-':>36} -> {ev.get('current_id') or '-':<36} {who}")
                offsets[f] = fh.tell()
        if not args.follow:
            break
        time.sleep(1.0)


if __name__ == "__main__":
    main()
