"""Pydantic models describing a tenant configuration.

A tenant config is a YAML file (see ``configs/tenants/demo.yaml``) layered on
top of ``aurora/config/defaults.yaml``. Nothing tenant-specific is hard-coded
anywhere in the engine: blocking strategies, feature weights, thresholds,
blocklists and cluster-hygiene limits all come from here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

DEFAULTS_PATH = Path(__file__).with_name("defaults.yaml")


class BlockingStrategy(BaseModel):
    """One blocking key definition.

    ``kind`` selects the key builder in :mod:`aurora.blocking.strategies`.
    ``max_block_size`` guards against over-large buckets (quadratic blowup).
    """

    name: str
    kind: str
    enabled: bool = True
    max_block_size: int = 200
    params: dict[str, Any] = Field(default_factory=dict)


class BlockingConfig(BaseModel):
    strategies: list[BlockingStrategy] = Field(default_factory=list)
    max_pairs: int = 5_000_000


class BlocklistConfig(BaseModel):
    """Known-garbage values stripped before blocking and graph building."""

    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    names: list[str] = Field(default_factory=list)
    email_domains: list[str] = Field(default_factory=list)


class ScoringConfig(BaseModel):
    """Ordinal-regression style scorer.

    ``mode`` is ``config`` (weighted sum with fixed thresholds) or ``learned``
    (logistic model fitted on labelled pairs, then quantised into 0..5 bins).
    ``thresholds`` are the five ordered cut points between categories
    0 (non-match), 1 (weak), 2 (moderate), 3 (high), 4 (excellent), 5 (exact).
    """

    mode: str = "config"
    weights: dict[str, float] = Field(default_factory=dict)
    bias: float = 0.0
    thresholds: list[float] = Field(default_factory=lambda: [0.5, 1.5, 2.5, 3.5, 4.5])
    edge_keep_threshold: float = 3.0
    deterministic_keys: list[str] = Field(default_factory=lambda: ["email", "phone"])
    hard_conflicts: dict[str, bool] = Field(default_factory=dict)
    model_path: str | None = None

    @model_validator(mode="after")
    def _check_thresholds(self) -> ScoringConfig:
        if len(self.thresholds) != 5 or any(
            a >= b for a, b in zip(self.thresholds, self.thresholds[1:], strict=False)
        ):
            raise ValueError("scoring.thresholds must be 5 strictly increasing values")
        return self


class HygieneConfig(BaseModel):
    """Cluster hygiene / over-merge guard."""

    supersized_threshold: int = 64
    hard_limit: int = 500
    weak_bridge_score: float = 3.5
    max_carve_iterations: int = 5


class StableIdConfig(BaseModel):
    hungarian_max_nodes: int = 2000
    namespace: str = "aurora-cdp"


class StorageConfig(BaseModel):
    format: str = "delta"  # delta | parquet
    lake_root: str = "data/lake"
    cdc_root: str = "data/cdc"
    raw_root: str = "data/raw"
    eval_root: str = "data/eval"


class SparkConfig(BaseModel):
    master: str = "local[*]"
    app_name: str = "aurora-cdp"
    shuffle_partitions: int = 16
    driver_memory: str = "4g"
    extra: dict[str, str] = Field(default_factory=dict)


class TenantConfig(BaseModel):
    tenant: str = "demo"
    sources: list[str] = Field(default_factory=list)
    blocking: BlockingConfig = Field(default_factory=BlockingConfig)
    blocklist: BlocklistConfig = Field(default_factory=BlocklistConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    hygiene: HygieneConfig = Field(default_factory=HygieneConfig)
    stable_id: StableIdConfig = Field(default_factory=StableIdConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    spark: SparkConfig = Field(default_factory=SparkConfig)
    nicknames: dict[str, str] = Field(default_factory=dict)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | Path | None = None, overrides: dict[str, Any] | None = None) -> TenantConfig:
    """Load defaults, overlay a tenant YAML, overlay dict overrides, validate."""
    with open(DEFAULTS_PATH) as fh:
        merged = yaml.safe_load(fh) or {}
    if path is not None:
        with open(path) as fh:
            merged = _deep_merge(merged, yaml.safe_load(fh) or {})
    if overrides:
        merged = _deep_merge(merged, overrides)
    return TenantConfig.model_validate(merged)
