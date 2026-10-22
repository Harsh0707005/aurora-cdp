"""Blocking strategies (Amperity: internals §2.4, dossier §3.8).

A strategy maps a record to zero or more blocking keys; records sharing a key form a block and every pair in
the block becomes a candidate pair. Blocks larger than the configured limit are skipped and logged (this is a
documented cause of under-clustering, so the skipped blocks are persisted for QA).
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations

log = logging.getLogger(__name__)


@dataclass
class BlockingResult:
    pairs: set[tuple[str, str]] = field(default_factory=set)
    keys: list[tuple[str, str, str, str]] = field(default_factory=list)  # (bk, datasource, pk, strategy)
    skipped: list[tuple[str, str, int, int]] = field(default_factory=list)  # (strategy, bk, size, limit)
    block_count: int = 0

    @property
    def pair_count(self) -> int:
        return len(self.pairs)


def _fks(record: dict) -> dict[str, str]:
    raw = record.get("fk_json")
    if not raw:
        return {}
    try:
        return json.loads(raw) if isinstance(raw, str) else dict(raw)
    except json.JSONDecodeError:
        return {}


def blocking_keys_for(record: dict, strategy: dict) -> list[tuple[str, str]]:
    """Return [(strategy_name, key)] for one record under one strategy."""
    kind = strategy["type"]
    name = strategy.get("name", kind)
    if kind == "email":
        v = record.get("email_norm")
        return [(name, v)] if v else []
    if kind == "phone":
        v = record.get("phone_match")
        return [(name, v)] if v else []
    if kind == "name_postal":
        g, s, p = record.get("given_name_canon"), record.get("surname_norm"), record.get("postal_norm")
        if g and s and p:
            return [(name, f"{g[:3]}:{s}:{p}")]
        return []
    if kind == "name_birthdate":
        g, s, b = record.get("given_name_canon"), record.get("surname_norm"), record.get("birthdate_norm")
        if g and s and b:
            return [(name, f"{g[:3]}:{s[:1]}:{b}")]
        return []
    if kind == "loy_id":
        v = record.get("loy_id_norm")
        return [(name, v)] if v else []
    if kind == "ck":
        v = record.get("ck")
        return [(name, str(v))] if v else []
    if kind == "fk":
        return [(f"fk-{ns.removeprefix('fk-')}", f"{ns}:{v}") for ns, v in _fks(record).items()]
    raise ValueError(f"unknown blocking strategy type: {kind}")


def build_blocks(records: dict[str, dict], cfg) -> BlockingResult:
    """records: rid -> preprocessed record. cfg: the `blocking` config section."""
    limit = int(cfg.get("block_size_limit", 100))
    fk_limit = int(cfg.get("fk_block_size_limit", 1000))
    strategies = cfg.get("strategies", [])
    blocks: dict[tuple[str, str], list[str]] = defaultdict(list)
    result = BlockingResult()
    for rid in sorted(records):
        rec = records[rid]
        for strategy in strategies:
            for sname, key in blocking_keys_for(rec, strategy):
                blocks[(sname, key)].append(rid)
                result.keys.append((key, rec["datasource"], rec["pk"], sname))
    for (sname, key), members in blocks.items():
        size = len(members)
        if size < 2:
            continue
        cap = fk_limit if sname.startswith("fk-") else limit
        if size > cap:
            result.skipped.append((sname, key, size, cap))
            log.warning("skipping oversized block strategy=%s key=%s size=%d limit=%d", sname, key, size, cap)
            continue
        result.block_count += 1
        for a, b in combinations(sorted(members), 2):
            result.pairs.add((a, b))
    return result
