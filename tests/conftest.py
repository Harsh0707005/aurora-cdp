import pytest


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    """Isolated workspace + outputs dir so tests never touch ./.aurora or ./outputs."""
    ws = tmp_path / "ws"
    out = tmp_path / "outputs"
    monkeypatch.setenv("AURORA_WORKSPACE", str(ws))
    monkeypatch.chdir(tmp_path)
    return ws, out
