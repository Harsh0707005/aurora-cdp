# Build log / changelog

Running record of what was built, by which model, and the key decisions.

**Implementer:** Claude Code, model `claude-fable-5-1` (Fable 5.1), single
headless session, no subagent delegation.

## 2026-10-22 — initial build

### Decisions
- **Spec reconciliation.** Two briefs were received; the later one (package
  `aurora/`, Delta-first storage, SciPy Hungarian, Jinja+HTMX UI, port 8000)
  supersedes the first. Ideas from the first brief that still fit were kept:
  jitter event taxonomy (added / deleted / merged / recognized / split /
  split_merged), `data/runs/<job_id>/summary.json`, one-line
  `JITTER SUMMARY:` stdout, Snowflake + Delta DDL.
- **Python 3.12 runtime.** No 3.11 interpreter on this Mac; `pyproject`
  declares `>=3.11`. PySpark 3.5 needs `setuptools` on 3.12 for the
  `distutils` shim — added as an explicit dependency.
- **PySpark 3.5.9 + delta-spark 3.3.3** pinned together (the globally
  installed PySpark 4.1 has no matching delta-spark release).
- **Delta with Parquet fallback.** `aurora.io.deltaio.build_spark` probes a
  tiny Delta write; on any failure (no jars / offline) it rebuilds a plain
  session and records the error in the run summary. The API reads tables
  without Spark by replaying `_delta_log` with pyarrow.
- **Scoring.** Config mode = weighted sum → five ordered thresholds → 0..5
  category with a continuous score (category + position inside the bin).
  Deterministic keys (email / phone / loyalty FK) short-circuit to `exact`;
  hard conflicts (DOB disagreement) cap the category at `moderate` so the
  pair can never become an edge. Learned mode = sklearn logistic + calibrated
  bins; grid-search tuner on labelled pairs.
- **Stable IDs.** Max-overlap bipartite matching on `(datasource, pk)`
  overlap counts. Bipartite graph decomposed into connected blocks; blocks
  under `hungarian_max_nodes` use `scipy.optimize.linear_sum_assignment`,
  larger ones use greedy largest-overlap-first. Split → only the largest
  fragment keeps the ID; merge → largest-overlap predecessor donates its ID.
  Ties broken by smaller old ID for run-to-run determinism.
- **Workspace hygiene.** A pre-existing, unrelated `aurora_cdp/` (DuckDB)
  package, its `Makefile`, and `docs/research/` copies were found in the
  workspace. They were left in place; the old Makefile was moved to
  `aurora_cdp/Makefile` so the spec'd `make` targets can live at the root, and
  `docs/research/` is git-ignored (reference material, not project code).

### Milestones
- [x] Config schema + defaults + demo tenant
- [x] Standardisation utils, deterministic `aurora_id` (UUIDv5)
- [x] Synthetic generator with truth labels and drift variant
- [x] Blocking strategies with block-size guard and diagnostics
- [x] Pairwise features (rapidfuzz JW / Damerau-Levenshtein)
- [x] Ordinal scorer (config + learned) and tuner
- [x] Union-find components + over-merge hygiene
- [x] Stable-ID max-overlap mapping (Hungarian / greedy)
- [x] CDC tables, JSONL sink, Kafka stub
- [x] Delta/Parquet lake I/O and Spark-free reader
- [x] End-to-end runner
- [ ] Evaluation suite
- [ ] FastAPI + Jinja/HTMX UI
- [ ] Snowflake / Delta DDL
- [ ] Tests, Makefile, Docker, docs
