"""Stable identifier helpers.

``aurora_id`` is a UUIDv5 derived from a tenant namespace and a *cluster seed*.
On the first run the seed is the lexicographically smallest ``(datasource, pk)``
in the cluster; on later runs the seed is inherited through max-overlap
mapping, so the ID never changes while a cluster is "recognised".
"""

from __future__ import annotations

import uuid

ROOT_NAMESPACE = uuid.UUID("6f1c2a2e-7b0e-4a6c-9c0e-a0a0a00000cd")


def tenant_namespace(name: str) -> uuid.UUID:
    return uuid.uuid5(ROOT_NAMESPACE, name)


def aurora_id_from_seed(namespace: str, seed: str) -> str:
    """Deterministic aurora_id for a cluster seed."""
    return str(uuid.uuid5(tenant_namespace(namespace), seed))


def cluster_seed(members: list[tuple[str, str]]) -> str:
    """Smallest (datasource, pk) pair, rendered as ``ds:pk``."""
    ds, pk = min(members)
    return f"{ds}:{pk}"


def new_job_id(ts: str | None = None) -> str:
    from datetime import datetime, timezone

    return ts or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
