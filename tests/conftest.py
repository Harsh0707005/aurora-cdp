import pytest

# Fail fast with one clear message instead of a collection error per module when the project is not installed
# in the interpreter running pytest (the engine's runtime deps are declared in pyproject.toml).
try:
    import duckdb  # noqa: F401
    import rapidfuzz  # noqa: F401
except ImportError as exc:  # pragma: no cover - environment guard
    pytest.exit(
        f"aurora-cdp runtime dependency missing in this interpreter ({exc}). Install the project first: "
        "`make install` (creates .venv) or `pip install -e '.[dev]'`, then run `.venv/bin/python -m pytest tests`.",
        returncode=2,
    )


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    """Isolated workspace + outputs dir so tests never touch ./.aurora or ./outputs."""
    ws = tmp_path / "ws"
    out = tmp_path / "outputs"
    monkeypatch.setenv("AURORA_WORKSPACE", str(ws))
    monkeypatch.chdir(tmp_path)
    return ws, out
