"""Typer CLI. Every command prints a one-line summary and the path to any outputs."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from aurora_cdp import __version__
from aurora_cdp.config import load_config
from aurora_cdp.storage.duck import connect, init_schema, latest_run_id

app = typer.Typer(help="Aurora CDP command line", no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)
stitch_app = typer.Typer(help="Identity resolution (Stitch) commands", invoke_without_command=True, pretty_exceptions_enable=False)
app.add_typer(stitch_app, name="stitch")
console = Console()

_config_opt = typer.Option(None, "--config", "-c", help="Optional aurora.yaml overlay")
_workspace_opt = typer.Option(None, "--workspace", "-w", help="Workspace dir (default .aurora)")


labels_app = typer.Typer(help="Stitch labels: operator-forced merges / splits persisted in the workspace", pretty_exceptions_enable=False)
app.add_typer(labels_app, name="labels")


@labels_app.command("add")
def labels_add(
    left: str = typer.Argument(..., help="datasource|pk"),
    right: str = typer.Argument(..., help="datasource|pk"),
    label: str = typer.Argument(..., help="merge | split"),
    note: str | None = typer.Option(None, "--note"),
    by: str | None = typer.Option(None, "--by"),
    config: str = _config_opt,
    workspace: str = _workspace_opt,
) -> None:
    """Persist one label; it is applied by every following stitch run."""
    from aurora_cdp.stitch.labels import add_label

    cfg = _cfg(config, workspace)
    con = connect(cfg.db_path)
    try:
        init_schema(con)
        lid = add_label(con, tuple(left.split("|", 1)), tuple(right.split("|", 1)), label, by, note)
        typer.echo(f"label {lid}: {left} {label} {right}")
    finally:
        con.close()


@labels_app.command("import")
def labels_import(path: str = typer.Argument(..., help="labels CSV"), by: str | None = typer.Option(None, "--by"), config: str = _config_opt, workspace: str = _workspace_opt) -> None:
    from aurora_cdp.stitch.labels import import_labels_file

    cfg = _cfg(config, workspace)
    con = connect(cfg.db_path)
    try:
        init_schema(con)
        typer.echo(f"imported {import_labels_file(con, path, by)} labels from {path}")
    finally:
        con.close()


@labels_app.command("list")
def labels_list(config: str = _config_opt, workspace: str = _workspace_opt, all: bool = typer.Option(False, "--all", help="include inactive")) -> None:
    cfg = _cfg(config, workspace)
    con = connect(cfg.db_path, read_only=True)
    try:
        rows = con.execute(
            "SELECT label_id, left_datasource || '|' || left_pk, label, right_datasource || '|' || right_pk, created_at, active, note FROM stitch_labels"
            + ("" if all else " WHERE active") + " ORDER BY created_at"
        ).fetchall()
        for r in rows:
            typer.echo("\t".join(str(x) for x in r))
        typer.echo(f"{len(rows)} labels")
    finally:
        con.close()


household_app = typer.Typer(help="Households: persistent household ids built from evidence edges", pretty_exceptions_enable=False)
app.add_typer(household_app, name="household")


@household_app.command("build")
def household_build(config: str = _config_opt, workspace: str = _workspace_opt, stitch_run: str | None = typer.Option(None, "--run-id")) -> None:
    """Observe evidence for the latest (or given) stitch run and (re)assign stable household ids."""
    from aurora_cdp.profile.households import build_households

    cfg = _cfg(config, workspace)
    con = connect(cfg.db_path)
    try:
        init_schema(con)
        r = build_households(con, cfg, stitch_run)
        m = r.metrics
        typer.echo(f"household run {r.run_id}: customers={m['customers']} households={m['households']} multi={m['multi_member_households']} "
                   f"evidence new/refreshed/expired={m['evidence_new']}/{m['evidence_refreshed']}/{m['evidence_expired']} jitter={m['jitter'].get('jitter_pct')}%")
    finally:
        con.close()


@household_app.command("show")
def household_show(aurora_id: str, config: str = _config_opt, workspace: str = _workspace_opt) -> None:
    from aurora_cdp.profile.households import household_of

    cfg = _cfg(config, workspace)
    con = connect(cfg.db_path, read_only=True)
    try:
        h = household_of(con, aurora_id)
        typer.echo("no household" if h is None else json.dumps(h, default=str, indent=1))
    finally:
        con.close()


@household_app.command("add-relationship")
def household_add_relationship(left: str, right: str, kind: str = typer.Argument(..., help="registry | gift | account_owner | ..."),
                               source: str | None = typer.Option(None, "--source"), config: str = _config_opt, workspace: str = _workspace_opt) -> None:
    from aurora_cdp.profile.households import add_relationship

    cfg = _cfg(config, workspace)
    con = connect(cfg.db_path)
    try:
        init_schema(con)
        add_relationship(con, tuple(left.split("|", 1)), tuple(right.split("|", 1)), kind, source)
        typer.echo(f"relationship {left} -{kind}- {right} recorded")
    finally:
        con.close()


@labels_app.command("remove")
def labels_remove(label_id: str, config: str = _config_opt, workspace: str = _workspace_opt) -> None:
    cfg = _cfg(config, workspace)
    con = connect(cfg.db_path)
    try:
        con.execute("UPDATE stitch_labels SET active = FALSE WHERE label_id = ?", [label_id])
        typer.echo(f"deactivated {label_id}")
    finally:
        con.close()


def _cfg(config: str | None, workspace: str | None):
    overrides = {"workspace": workspace} if workspace else None
    return load_config(config, overrides=overrides)


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


@app.callback()
def main(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    _setup_logging(verbose)


@app.command()
def version() -> None:
    console.print(f"aurora-cdp {__version__}")


@app.command("init-db")
def init_db(config: str = _config_opt, workspace: str = _workspace_opt) -> None:
    """Create the DuckDB file and apply the versioned schema."""
    cfg = _cfg(config, workspace)
    con = connect(cfg.db_path)
    try:
        applied = init_schema(con)
    finally:
        con.close()
    console.print(f"schema ready (applied versions: {applied or 'none, already current'}) -> {cfg.db_path}")


@app.command()
def ingest(
    path: Path = typer.Argument(..., help="CSV or Parquet file"),
    source: str = typer.Option(..., "--source", "-s"),
    feed: str = typer.Option(..., "--feed", "-f"),
    mode: str = typer.Option("incremental", "--mode", help="full | incremental"),
    mapping: Path | None = typer.Option(None, "--mapping", "-m", help="YAML semantic mapping; when given, silver tables are rebuilt for the source"),
    config: str = _config_opt,
    workspace: str = _workspace_opt,
) -> None:
    """Land a file into bronze (row-hash dedupe) and optionally tag + preprocess it."""
    from aurora_cdp.ingestion.landing import ingest_file
    from aurora_cdp.orchestration.pipeline import tag_feed

    cfg = _cfg(config, workspace)
    con = connect(cfg.db_path)
    try:
        init_schema(con)
        r = ingest_file(con, path, source, feed, mode)
        tagged = tag_feed(con, cfg, source, feed, yaml.safe_load(mapping.read_text())) if mapping else 0
    finally:
        con.close()
    console.print(f"{r.summary()} tagged={tagged} -> {cfg.db_path}")


@stitch_app.callback()
def stitch(
    ctx: typer.Context,
    mode: str = typer.Option("full", "--mode", help="full | incremental"),
    threshold: float | None = typer.Option(None, "--threshold", help="override matcher.match_threshold"),
    config: str = _config_opt,
    workspace: str = _workspace_opt,
) -> None:
    """Run identity resolution on the workspace (default) or use `stitch run` / `stitch export`."""
    if ctx.invoked_subcommand is not None:
        return
    from aurora_cdp.stitch.run import run_stitch

    cfg = _cfg(config, workspace)
    if threshold is not None:
        cfg = load_config(config, overrides={"workspace": cfg["workspace"], "matcher": {"match_threshold": threshold}})
    con = connect(cfg.db_path)
    try:
        init_schema(con)
        r = run_stitch(con, cfg, mode=mode)
    finally:
        con.close()
    console.print(f"{r.summary()} -> {cfg.db_path}")


@stitch_app.command("run")
def stitch_run(
    input: Path = typer.Option(..., "--input", "-i", help="CSV/Parquet of source records (see docs/adapter-contract.md)"),
    out: Path = typer.Option(Path("assignments.csv"), "--out", "-o"),
    scores_out: Path | None = typer.Option(None, "--scores-out", help="optional pair-level scores CSV/Parquet"),
    mapping: Path | None = typer.Option(None, "--mapping", "-m", help="YAML semantic mapping (default: columns already semantic)"),
    previous: Path | None = typer.Option(None, "--previous", help="previous assignments file to compute stable IDs / churn against"),
    datasource: str = typer.Option("input", "--datasource", help="datasource name when the input has no datasource column"),
    threshold: float | None = typer.Option(None, "--threshold"),
    keep_workspace: bool = typer.Option(False, "--keep-workspace"),
    config: str = _config_opt,
    workspace: str = _workspace_opt,
) -> None:
    """Scoring-harness adapter: stitch a standalone file and write (source_record_id, unified_id, run_date)."""
    from aurora_cdp.adapter import run_on_file

    cfg = _cfg(config, workspace)
    if threshold is not None:
        cfg = load_config(config, overrides={"workspace": cfg["workspace"], "matcher": {"match_threshold": threshold}})
    r = run_on_file(cfg, input, out, scores_out, mapping, datasource, keep_workspace=keep_workspace, previous_assignments=previous)
    m = r["metrics"]
    console.print(
        f"stitched {r['rows']} records -> clusters={m['clusters']} edges={m['edges']} jitter={m['jitter'].get('jitter_pct')}% ; assignments -> {r['assignments']}"
        + (f" ; scores -> {r['scores']}" if "scores" in r else "")
    )


@stitch_app.command("export")
def stitch_export(
    out: Path = typer.Option(Path("outputs/assignments.csv"), "--out", "-o"),
    scores_out: Path | None = typer.Option(None, "--scores-out"),
    run_id: str | None = typer.Option(None, "--run-id"),
    config: str = _config_opt,
    workspace: str = _workspace_opt,
) -> None:
    """Export the assignment table of a workspace run (latest by default)."""
    from aurora_cdp.adapter import export_assignments

    r = export_assignments(_cfg(config, workspace), out, run_id, scores_out)
    console.print(f"exported {r['rows']} assignments for run {r['run_id']} -> {r['assignments']}" + (f" ; scores -> {r['scores']}" if "scores" in r else ""))


@app.command()
def resolve(
    input: Path = typer.Option(..., "--input", "-i", help="csv | parquet | jsonl | json of source records"),
    output: Path = typer.Option(..., "--output", "-o", help="assignments output: csv | parquet | jsonl"),
    config: str = _config_opt,
    scores: Path | None = typer.Option(None, "--scores", help="optional pair-level scores output"),
    previous: Path | None = typer.Option(None, "--previous", help="previous assignments for stable IDs / churn"),
    mapping: Path | None = typer.Option(None, "--mapping", "-m", help="semantic mapping yaml for raw column names"),
    datasource: str = typer.Option("input", "--datasource"),
    threshold: float | None = typer.Option(None, "--threshold"),
) -> None:
    """Stable external entrypoint (docs/interfaces.md): resolve a file of records into clusters + stable IDs."""
    from aurora_cdp.adapters.resolver import resolve_file

    res = resolve_file(input, output, config, scores, previous, mapping, datasource, threshold)
    m = res.metrics
    console.print(
        f"resolved {len(res.assignments)} records -> clusters={m.get('clusters')} edges={m.get('edges')} "
        f"jitter={m.get('jitter', {}).get('jitter_pct')}% run={res.run_id} ; assignments -> {output}"
        + (f" ; scores -> {scores}" if scores else "")
    )


@app.command()
def profile(config: str = _config_opt, workspace: str = _workspace_opt) -> None:
    """Build golden records (survivorship) and the profile timeline for the latest stitch run."""
    from aurora_cdp.profile.builder import build_profiles

    cfg = _cfg(config, workspace)
    con = connect(cfg.db_path)
    try:
        r = build_profiles(con, cfg)
    finally:
        con.close()
    console.print(f"{r.summary()} -> {cfg.db_path}")


@app.command()
def segment(
    name: str = typer.Argument(..., help="segment name (saved) or name for a new definition"),
    definition: Path | None = typer.Option(None, "--definition", "-d", help="YAML/JSON segment definition to save"),
    export: bool = typer.Option(True, "--export/--no-export", help="export members as CSV"),
    config: str = _config_opt,
    workspace: str = _workspace_opt,
) -> None:
    """Evaluate a saved segment (or save a new one) and export members to CSV."""
    from aurora_cdp.audiences.destinations import export_csv
    from aurora_cdp.audiences.segmenter import evaluate_segment, load_segment, save_segment

    cfg = _cfg(config, workspace)
    con = connect(cfg.db_path)
    try:
        if definition:
            spec = yaml.safe_load(definition.read_text())
            spec["name"] = name
            save_segment(con, spec)
        else:
            spec = load_segment(con, name)
        r = evaluate_segment(con, spec)
        path = export_csv(con, name, r.members, cfg.outputs_path) if export else None
    finally:
        con.close()
    console.print(f"{r.summary()}" + (f" -> {path}" if path else ""))


@app.command()
def report(run_id: str | None = typer.Option(None, "--run-id"), config: str = _config_opt, workspace: str = _workspace_opt) -> None:
    """Print QA metrics for a stitch run and write a markdown report under outputs/."""
    cfg = _cfg(config, workspace)
    con = connect(cfg.db_path, read_only=True)
    try:
        rid = run_id or latest_run_id(con)
        if rid is None:
            raise typer.Exit(code=1)
        row = con.execute("SELECT mode, started_at, metrics_json FROM stitch_runs WHERE run_id = ?", [rid]).fetchone()
        metrics = json.loads(row[2]) if row and row[2] else {}
        skipped = con.execute("SELECT strategy, bk, block_size FROM stitch_skipped_blocks WHERE run_id = ? ORDER BY block_size DESC LIMIT 10", [rid]).fetchall()
        blocklisted = con.execute("SELECT semantic, value, distinct_count FROM stitch_blocklist_values WHERE run_id = ? LIMIT 10", [rid]).fetchall()
    finally:
        con.close()
    table = Table(title=f"Stitch run {rid} ({row[0]})")
    table.add_column("metric")
    table.add_column("value")
    for k in ["records", "pairs_blocked", "pairs_scored", "edges", "match_rate", "clusters", "multi_record_clusters", "max_cluster_size", "split_components", "supersized_components", "skipped_blocks", "blocklisted_values"]:
        table.add_row(k, str(metrics.get(k)))
    j = metrics.get("jitter", {})
    table.add_row("jitter_pct", f"{j.get('jitter_pct')} (changed {j.get('records_changed')}/{j.get('records_compared')}, minted {j.get('ids_minted')}, retired {j.get('ids_retired')}, alert={j.get('alert')})")
    table.add_row("cluster_size_distribution", json.dumps(metrics.get("cluster_size_distribution")))
    console.print(table)
    out = cfg.outputs_path / f"report_{rid}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Stitch run {rid}", "", f"mode: {row[0]}  started: {row[1]}", "", "| metric | value |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in metrics.items() if k not in {"timings_sec", "match_category_counts"}]
    lines += ["", "## Skipped oversized blocks", ""] + [f"- {s} `{b}` size={n}" for s, b, n in skipped]
    lines += ["", "## Blocklisted values", ""] + [f"- {s} `{v}` distinct={n}" for s, v, n in blocklisted]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    console.print(f"report written -> {out}")


@app.command()
def demo(
    people: int = typer.Option(700, "--people", help="number of simulated people"),
    fast: bool = typer.Option(False, "--fast", help="small dataset for tests"),
    config: str = _config_opt,
    workspace: str = _workspace_opt,
) -> None:
    """Synthesize multi-source data and run ingestion -> stitch (x2) -> profiles -> segment -> CSV export."""
    from aurora_cdp.demo import run_demo

    cfg = _cfg(config, workspace)
    r = run_demo(cfg, people=people, fast=fast)
    m1, m2 = r["run1"]["metrics"], r["run2"]["metrics"]
    console.print(
        f"demo complete: run1 clusters={m1['clusters']} ; run2 clusters={m2['clusters']} jitter={m2['jitter']['jitter_pct']}% "
        f"(minted {m2['jitter']['ids_minted']}) ; profiles={r['profiles']} -> db {r['db']} ; audience csv {r['export']}"
    )


@app.command()
def tune(
    quick: bool = typer.Option(True, "--quick/--full", help="quick = 400 people, default threshold grid"),
    thresholds: str | None = typer.Option(None, "--thresholds", help="comma-separated, e.g. 2.5,3,3.5"),
    docs_path: Path = typer.Option(Path("docs/tuning.md"), "--docs"),
    config: str = _config_opt,
    workspace: str = _workspace_opt,
) -> None:
    """Sweep match thresholds on synthetic labelled data; write docs/tuning.md and .aurora/last_best.yaml."""
    from aurora_cdp.tuning import pick_best, sweep, write_results

    cfg = load_config(config, overrides={"workspace": workspace} if workspace else None, use_last_best=False)
    grid = [float(t) for t in thresholds.split(",")] if thresholds else None
    people = 400 if quick else 1500
    table = sweep(cfg, grid, people=people, quick=quick)
    min_p = cfg.tuning.get("min_precision")
    best = pick_best(table, min_p)
    last_best = cfg.workspace_path / "last_best.yaml"
    write_results(table, best, docs_path, last_best, people, min_p)
    console.print(table.to_string(index=False))
    console.print(f"best threshold={best} (precision>={min_p} if attainable, then F1, lowest churn, closest to 3.0) -> {last_best} ; table -> {docs_path}")


@app.command("pipeline")
def pipeline_cmd(
    spec: Path = typer.Argument(..., help="pipeline YAML"),
    config: str = _config_opt,
    workspace: str = _workspace_opt,
) -> None:
    """Run a YAML-defined pipeline (databases -> feeds -> stitch -> profile -> segments -> destinations)."""
    from aurora_cdp.orchestration.pipeline import append_run_history, load_pipeline, run_pipeline

    cfg = _cfg(config, workspace)
    con = connect(cfg.db_path)
    try:
        init_schema(con)
        r = run_pipeline(con, cfg, load_pipeline(spec))
    finally:
        con.close()
    hist = append_run_history(cfg, r)
    console.print(f"{r.summary()} -> history {hist}" + (f" ; outputs {', '.join(r.outputs)}" if r.outputs else ""))


@app.command()
def schedule(
    spec: Path = typer.Argument(..., help="pipeline YAML"),
    interval: int = typer.Option(300, "--interval", help="seconds between runs"),
    max_runs: int | None = typer.Option(None, "--max-runs"),
    config: str = _config_opt,
    workspace: str = _workspace_opt,
) -> None:
    """Run a pipeline on a fixed interval (minimal local scheduler); history in <workspace>/runs.jsonl."""
    from aurora_cdp.orchestration.scheduler import run_forever

    cfg = _cfg(config, workspace)
    n = run_forever(cfg, spec, interval, max_runs)
    console.print(f"scheduler stopped after {n} run(s) -> {cfg.workspace_path / 'runs.jsonl'}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Start the FastAPI service (+ minimal UI at /ui)."""
    import uvicorn

    console.print(f"serving http://{host}:{port}  (UI: /ui, docs: /docs)")
    uvicorn.run("aurora_cdp.api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
