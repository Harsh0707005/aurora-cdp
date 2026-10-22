"""Stitch labels: operator-supplied forced merges and splits (Amperity: Stitch labels, internals §2.11).

A labels file is a CSV with the columns ``left_datasource, left_pk, right_datasource, right_pk, label`` where
``label`` is ``merge`` (the two records must end up in the same cluster) or ``split`` (they must never share a
cluster, directly or through other records). Labels are applied on top of scoring:

* ``merge`` adds a score-5 edge (``match_type = label_merge``, like a carried cluster edge);
* ``split`` removes any scored edge between the pair and installs a pair-level veto in the conflict-aware
  clustering (``cluster.cluster_indices(..., forbidden=...)``): a union that would put the two records in one
  cluster is rejected the same way a hard attribute conflict is.

Rows naming records that are not part of the run are counted (``labels_unmatched``) and ignored; malformed rows
(unknown label, missing columns, a record paired with itself, the same pair labelled both ways) are errors
because a silently ignored label is worse than a failed run.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

LABEL_COLUMNS = ("left_datasource", "left_pk", "right_datasource", "right_pk", "label")
LABEL_VALUES = ("merge", "split")


@dataclass
class StitchLabels:
    merge: list[tuple[str, str]] = field(
        default_factory=list
    )  # (rid, rid), rid = "datasource|pk", rid_a < rid_b
    split: list[tuple[str, str]] = field(default_factory=list)
    source: str | None = None

    def __len__(self) -> int:
        return len(self.merge) + len(self.split)


def load_labels(path: str | Path | None) -> StitchLabels:
    """Read the labels CSV (header required). Missing/unset path -> no labels (not an error)."""
    if not path:
        return StitchLabels()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"labels.file {str(p)!r} does not exist")
    out = StitchLabels(source=str(p))
    seen: dict[tuple[str, str], str] = {}
    with p.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in LABEL_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(
                f"labels file {str(p)!r} lacks columns {missing}; expected {list(LABEL_COLUMNS)}"
            )
        for n, row in enumerate(reader, start=2):
            vals = {c: (row.get(c) or "").strip() for c in LABEL_COLUMNS}
            if not any(vals.values()):
                continue
            if any(not vals[c] for c in LABEL_COLUMNS):
                raise ValueError(
                    f"labels file {str(p)!r} line {n}: every column must be filled: {row}"
                )
            label = vals["label"].lower()
            if label not in LABEL_VALUES:
                raise ValueError(
                    f"labels file {str(p)!r} line {n}: label must be one of {LABEL_VALUES}, got {vals['label']!r}"
                )
            a = f"{vals['left_datasource']}|{vals['left_pk']}"
            b = f"{vals['right_datasource']}|{vals['right_pk']}"
            if a == b:
                raise ValueError(
                    f"labels file {str(p)!r} line {n}: a record cannot be labelled against itself ({a})"
                )
            pair = (a, b) if a < b else (b, a)
            prev = seen.get(pair)
            if prev is not None and prev != label:
                raise ValueError(
                    f"labels file {str(p)!r} line {n}: pair {pair} is labelled both merge and split"
                )
            if prev is not None:
                continue
            seen[pair] = label
            (out.merge if label == "merge" else out.split).append(pair)
    log.info("loaded %d merge and %d split labels from %s", len(out.merge), len(out.split), p)
    return out


@dataclass
class ResolvedLabels:
    merge_left: np.ndarray  # record indices (idx), left < right
    merge_right: np.ndarray
    split_left: np.ndarray
    split_right: np.ndarray
    unmatched: int = 0

    @property
    def forbidden(self) -> list[tuple[int, int]]:
        return list(zip(self.split_left.tolist(), self.split_right.tolist(), strict=True))

    def as_metrics(self) -> dict:
        return {
            "labels_merge": int(len(self.merge_left)),
            "labels_split": int(len(self.split_left)),
            "labels_unmatched": int(self.unmatched),
        }


def resolve_labels(labels: StitchLabels, rid_to_idx: dict[str, int]) -> ResolvedLabels:
    """Map rid pairs onto record indices of the current run; pairs with an unknown record are counted, not applied."""
    unmatched = 0

    def pairs(items: list[tuple[str, str]]) -> tuple[np.ndarray, np.ndarray]:
        nonlocal unmatched
        lefts: list[int] = []
        rights: list[int] = []
        for a, b in items:
            ia, ib = rid_to_idx.get(a), rid_to_idx.get(b)
            if ia is None or ib is None:
                unmatched += 1
                continue
            lefts.append(min(ia, ib))
            rights.append(max(ia, ib))
        return np.array(lefts, dtype=np.int64), np.array(rights, dtype=np.int64)

    ml, mr = pairs(labels.merge)
    sl, sr = pairs(labels.split)
    return ResolvedLabels(ml, mr, sl, sr, unmatched)


def apply_split_labels(
    left: np.ndarray, right: np.ndarray, score: np.ndarray, resolved: ResolvedLabels
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """Drop scored edges between split-labelled pairs. Returns the filtered arrays and the number removed."""
    if len(resolved.split_left) == 0 or len(left) == 0:
        return left, right, score, 0
    lo, hi = np.minimum(left, right), np.maximum(left, right)
    banned = set(zip(resolved.split_left.tolist(), resolved.split_right.tolist(), strict=True))
    keep = np.array(
        [(a, b) not in banned for a, b in zip(lo.tolist(), hi.tolist(), strict=True)], dtype=bool
    )
    removed = int((~keep).sum())
    return left[keep], right[keep], score[keep], removed
