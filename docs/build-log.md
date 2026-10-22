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
- [x] Evaluation suite (`aurora/pipeline/eval.py`, `docs/aurora/evaluation.md`)
- [x] FastAPI + Jinja/HTMX UI (smoke-tested end to end against a 3k lake)
- [x] Snowflake / Delta DDL
- [x] Tests (16, ~40 s), `aurora/Makefile`, `aurora/docker/`, `docs/aurora/`

### Issues found and fixed during verification
- Delta appends failed across runs: all-null pandas columns arrived as `void`
  and int columns with NaN became `double`. `LakeIO.write_pandas` now casts
  null-typed columns to string, appends use `mergeSchema`, and the runner
  casts the CDC integer columns explicitly.
- A failed run could overwrite `Unified_Customer` before the stable-ID
  mapping was persisted, so a retry compared the run with itself (0 %
  jitter). Serving tables are now written only after all CDC tables are
  computed, and the previous assignment is snapshotted to
  `data/runs/<job_id>/prev_assignments.parquet`.
- Arrow nulls reached the standardiser as NaN floats and became the literal
  string `"nan"`; ~250 nameless rows then blocked and merged into one
  supersized cluster (pair precision 0.07). Nulls are coerced before
  standardising and `clean_text` treats NaN as null. Added `given_conflict`
  as a hard conflict so household members sharing phone/address do not merge.
  After the fix on the 3k sample: pair F1 0.94, B-cubed F1 0.986, run-2
  jitter 0.0 % / churn 0.04 %.
- API: `/profiles/by_pk` was shadowed by `/profiles/{aurora_id}` (route
  order); email/phone search used positions from a filtered frame; UUIDs in
  the UI search were treated as phone numbers.

### Shared workspace
A second Claude session (`aurora-cdp-10`) builds the sibling `aurora_cdp/`
(DuckDB) package in the same repo. Path split agreed over cross-session
messaging: this session owns `aurora/`, `configs/`, `data/`, `.tmp/`,
`docs/aurora/`, `docs/build-log.md`, `scripts/cdc_consumer.py` and its own
test files; the peer owns the root `Makefile`, `CHANGELOG.md`, `docker/`,
`deploy/`, top-level `docs/*.md` and the base `pyproject.toml` dependency set
(this session's deps live in the `[spark]` extra). Commits use explicit
pathspecs only.

