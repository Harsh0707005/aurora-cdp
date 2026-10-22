"""Configuration loading: defaults.yaml -> optional ./aurora.yaml -> .aurora/last_best.yaml."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

DEFAULTS_PATH = Path(__file__).with_name("defaults.yaml")


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in (overlay or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a mapping at the top level")
    return data


class Config(dict):
    """A dict with attribute-style access for nested sections (cfg.matcher.match_threshold)."""

    def __getattr__(self, item: str) -> Any:
        try:
            value = self[item]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(item) from exc
        return Config(value) if isinstance(value, dict) else value

    @property
    def workspace_path(self) -> Path:
        return Path(self["workspace"]).resolve()

    @property
    def db_path(self) -> Path:
        return self.workspace_path / self["db_file"]

    @property
    def outputs_path(self) -> Path:
        return Path(self["outputs_dir"]).resolve()


def load_config(
    path: str | os.PathLike[str] | None = None,
    overrides: dict[str, Any] | None = None,
    use_last_best: bool = True,
) -> Config:
    """Build the effective configuration.

    Order: packaged defaults -> `path` (or ./aurora.yaml if present) -> <workspace>/last_best.yaml
    (written by `aurora tune`) -> explicit `overrides`.
    """
    cfg = _read_yaml(DEFAULTS_PATH)
    user_path = Path(path) if path else Path("aurora.yaml")
    cfg = _deep_merge(cfg, _read_yaml(user_path))
    if use_last_best:
        last_best = Path(cfg["workspace"]) / "last_best.yaml"
        cfg = _deep_merge(cfg, _read_yaml(last_best))
    if overrides:
        cfg = _deep_merge(cfg, overrides)
    env_ws = os.environ.get("AURORA_WORKSPACE")
    if env_ws:
        cfg["workspace"] = env_ws
    return Config(cfg)
