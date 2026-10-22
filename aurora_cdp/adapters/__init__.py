"""Stable, documented entrypoints for external callers (see docs/interfaces.md).

Lazy re-exports so `python -m aurora_cdp.adapters.resolver` does not double-import the module.
"""

from __future__ import annotations

__all__ = ["ResolveResult", "resolve_file", "resolve_records"]


def __getattr__(name: str):
    if name in __all__:
        from . import resolver

        return getattr(resolver, name)
    raise AttributeError(name)
