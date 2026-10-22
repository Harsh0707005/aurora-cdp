"""Change-data-capture events and sinks.

Event ``type`` values:

* ``identity_assigned`` – a brand-new aurora_id was minted for a cluster.
* ``id_reissued`` – a record moved from one aurora_id to another.
* ``cluster_split`` – an old aurora_id's records now live in >1 cluster.
* ``cluster_merge`` – a new cluster absorbed >1 old aurora_ids.
* ``identity_retired`` – an old aurora_id no longer has any records.

Sinks are pluggable; the default writes newline-delimited JSON under
``data/cdc/<job_id>.jsonl``. A Kafka sink stub shows the interface.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


@dataclass
class CdcEvent:
    type: str
    job_id: str
    current_id: str | None
    previous_id: str | None
    datasource: str | None = None
    pk: str | None = None
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    lineage: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))


class Sink(Protocol):
    def emit(self, event: CdcEvent) -> None: ...
    def close(self) -> None: ...


class JsonlSink:
    def __init__(self, root: str | Path, job_id: str) -> None:
        self.path = Path(root) / f"{job_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "w")
        self.count = 0

    def emit(self, event: CdcEvent) -> None:
        self._fh.write(event.to_json() + "\n")
        self.count += 1

    def close(self) -> None:
        self._fh.close()


class KafkaSink:
    """Placeholder for a real broker; logs instead of sending."""

    def __init__(self, topic: str = "aurora.cdc") -> None:
        self.topic = topic
        self.count = 0

    def emit(self, event: CdcEvent) -> None:
        self.count += 1
        print(f"[kafka-stub] {self.topic} <- {event.to_json()[:120]}")

    def close(self) -> None:
        return None


def build_change_tables(
    cluster_events: "pd.DataFrame", prev_pks: "pd.DataFrame | None", new_pks: "pd.DataFrame", job_id: str
) -> tuple["pd.DataFrame", "pd.DataFrame"]:
    """Produce Unified_Changes_Clusters and Unified_Changes_PKs frames.

    ``prev_pks``/``new_pks`` columns: datasource, pk, aurora_id.
    """
    import pandas as pd

    ts = datetime.now(timezone.utc).isoformat()
    clusters = cluster_events.copy()
    clusters["job_id"] = job_id
    clusters["ts"] = ts
    clusters["lineage"] = "lineage:" + job_id + ":" + clusters["current_id"].fillna(clusters["previous_id"]).astype(str)
    clusters = clusters[["current_id", "previous_id", "change_type", "overlap", "new_size", "previous_size",
                         "fragments", "absorbed", "job_id", "ts", "lineage"]]

    if prev_pks is None or prev_pks.empty:
        pks = new_pks[["datasource", "pk", "aurora_id"]].rename(columns={"aurora_id": "current_id"})
        pks["previous_id"] = None
        pks["change_type"] = "added"
    else:
        m = new_pks[["datasource", "pk", "aurora_id"]].merge(
            prev_pks[["datasource", "pk", "aurora_id"]], on=["datasource", "pk"], how="outer",
            suffixes=("_new", "_old"), indicator=True,
        )
        m["current_id"] = m["aurora_id_new"]
        m["previous_id"] = m["aurora_id_old"]
        m["change_type"] = "unchanged"
        m.loc[m["_merge"] == "left_only", "change_type"] = "added"
        m.loc[m["_merge"] == "right_only", "change_type"] = "removed"
        moved = (m["_merge"] == "both") & (m["current_id"] != m["previous_id"])
        m.loc[moved, "change_type"] = "moved"
        pks = m.loc[m["change_type"] != "unchanged", ["datasource", "pk", "current_id", "previous_id", "change_type"]]
    pks = pks.copy()
    pks["job_id"] = job_id
    pks["ts"] = ts
    pks["lineage"] = "lineage:" + job_id + ":" + pks["current_id"].fillna(pks["previous_id"]).astype(str)
    return clusters.reset_index(drop=True), pks.reset_index(drop=True)


def emit_events(sink: Sink, clusters: "pd.DataFrame", pks: "pd.DataFrame", job_id: str) -> int:
    """Translate the two change tables into CDC events on ``sink``."""
    n = 0
    type_map = {"added": "identity_assigned", "deleted": "identity_retired", "merged": "cluster_merge",
                "split": "cluster_split", "split_merged": "cluster_split"}
    for r in clusters.itertuples(index=False):
        if r.change_type == "recognized":
            continue
        sink.emit(CdcEvent(type=type_map.get(r.change_type, r.change_type), job_id=job_id,
                           current_id=r.current_id, previous_id=r.previous_id, lineage=r.lineage,
                           details={"change_type": r.change_type, "overlap": int(r.overlap),
                                    "new_size": int(r.new_size), "previous_size": int(r.previous_size)}))
        n += 1
        if r.change_type == "split_merged":
            sink.emit(CdcEvent(type="cluster_merge", job_id=job_id, current_id=r.current_id,
                               previous_id=r.previous_id, lineage=r.lineage,
                               details={"change_type": r.change_type}))
            n += 1
    for r in pks.itertuples(index=False):
        if r.change_type == "moved":
            sink.emit(CdcEvent(type="id_reissued", job_id=job_id, current_id=r.current_id,
                               previous_id=r.previous_id, datasource=r.datasource, pk=r.pk, lineage=r.lineage))
            n += 1
    return n
