# Architecture

Each component below names the Amperity behaviour it reproduces and the research section that documents it.
References: `[INT]` = `docs/research/amperity-internals-2026-10-14.md`, `[DOS]` =
`docs/research/amperity-master-dossier-2026-10-14.md`, `[SIM]` = `docs/research/amperity-explained-simply-2026-10-19.md`.

```
feeds (CSV/Parquet)
  └─ ingestion/landing.py      bronze_landing (schema-on-read JSON, row-hash dedupe, full/incremental)
      └─ ingestion/semantics.py   silver_unified_raw        (semantic tags: given_name, surname, email, phone, address group, loy_id, fk-*, pk, ck)
          └─ ingestion/normalize.py  silver_unified_preprocessed (Unified Preprocessed Raw analogue)
              └─ stitch/run.py
                   ├─ blocklist (auto bad-value detection)        stitch_blocklist_values
                   ├─ stitch/blocking.py   candidate pairs         stitch_blocking_keys, stitch_skipped_blocks
                   ├─ stitch/features.py + matcher.py  0-5 scores  stitch_scores
                   ├─ stitch/cluster.py    components → conflict-aware clusters → stitch_clusters
                   └─ stitch/stable_id.py  greedy max-overlap ID inheritance → id_ledger (SCD2),
                                            unified_changes_pk / unified_changes_clusters, jitter_reports
                  └─ profile/builder.py + survivorship.py  gold_merged_customers (SCD2), gold_profile_events
                       └─ views: unified_coalesced, identity_graph, customer_360
                            └─ audiences/segmenter.py → segment_members → destinations.py (CSV, webhook)
orchestration/pipeline.py   YAML DAG: databases → feeds → stitch → profile → segments → destinations
orchestration/scheduler.py  interval loop + runs.jsonl
api/main.py                 FastAPI (+ Jinja2 UI)      cli.py  Typer
```

## Component → Amperity behaviour

| Component | Amperity behaviour | Reference |
|---|---|---|
| `ingestion/landing.py` | Feeds land into domain tables; data is kept immutable/versioned (a full load retires, never deletes, prior rows) | `[INT]` §2.11, §3.2 |
| `ingestion/semantics.py` | Semantic tagging: `given-name`, `surname`, `email`, `phone`, address group, `birthdate`, `fk-*`, `pk`, `ck`; mandatory per feed | `[INT]` §2.2, `[DOS]` §4.1 |
| `ingestion/normalize.py` | Preprocessing: email → local@domain, strip `+tag`, junk local parts NULLed; phone last-10-digits; address abbreviation expansion; nickname table | `[INT]` §2.3, `[DOS]` §3.8 (`stitch_nicknames`) |
| `stitch/run.py::apply_blocklist` | Automatic bad-value detection: email with >20 given names / surnames, phone >20, address >40 → ignored before graph building | `[INT]` §5, `[DOS]` §3.8 |
| `stitch/blocking.py` | Blocking strategies (`given-name(3)+surname+postal`, `given-name(3)+surname(1)+birthdate`, email, phone, fk), blocking size limit 100 / fk limit 1000; skipped blocks persisted; Stitch Blocking Keys table | `[INT]` §2.4, `[DOS]` §3.8 |
| `stitch/features.py` | Pairwise similarity signatures: edit distance on names/email, token similarity on address, exact keys | `[INT]` §2.5 |
| `stitch/matcher.py` | 0–5 score bands (weak/moderate/high/excellent/exact), default threshold 3.0, ordered deterministic rules first (Rules Editor), hard-conflict label, `trivial_duplicate` / `scored` match types, Stitch Scores table incl. non-merges | `[INT]` §2.5, §2.8, `[DOS]` §3.8 |
| `stitch/cluster.py` | Connected components are not the answer; conflict-free clustering (merge in descending score, refuse merges that introduce a hard conflict); BFS partitioning of supersized components; component / supersized ids persisted for QA | `[INT]` §2.7–2.9 |
| `stitch/stable_id.py` | Stable ID assignment: edges current↔previous weighted by shared PKs, sorted desc, ties by ascending id, greedy, one successor per old id; new entities mint UUIDs; deleted entities retire; jitter metric + 2% alert; Unified Changes PKs / Clusters | `[INT]` §1.2–1.6 |
| `storage/schema.sql` | Unified Preprocessed Raw, Unified Coalesced, Stitch Scores, Stitch Blocking Keys, Identity Graph (`amperity_id × datasource × COALESCE(ck, pk)`), Unified Changes *, Merged Customers, Customer 360; immutable generations keyed by run_id | `[INT]` §3.3, §2.11 |
| `profile/survivorship.py` | Source_Priority / Field_Priority (unassigned = 999), recency via `update-dt`, provenance per attribute; one row per ID | `[INT]` §2.10 |
| `profile/builder.py` | Merged Customers + Customer 360 (+ interaction rollups keyed by ID via fk) | `[INT]` §3.3, §4.2 |
| `audiences/segmenter.py` | Segments as filters over Customer 360 keyed by the unique ID | `[INT]` §4.1 |
| `audiences/destinations.py` | Activations to destinations (CSV now, webhook stub) | `[INT]` §4.4 |
| `orchestration/*` | Workflows / scheduled couriers; run history | `[INT]` §4.4 |
| `api/main.py` | Profile API (read-only lookups), change feed, Stitch QA dashboard | `[INT]` §3.4, §5 |
| `tuning.py` + `aurora tune` | Threshold is the documented lever controlling over/under-merge and churn; sweep reports precision/recall/false-merge/ID churn | `[DOS]` §3.8, `[INT]` §1.4 |
| `adapter.py` | Assignment export for the external scoring harness (see `adapter-contract.md`) | — |

## Data flow per Stitch run (`stitch/run.py`)

1. Load the latest preprocessed row per `(datasource, pk)`; apply the bad-value blocklist.
2. Blocking → candidate pairs (+ keys and skipped blocks persisted).
3. Incremental mode: keep only pairs touching records changed since the last run; carry previous
   cluster memberships as `carried` edges (score 5.0) so unchanged clusters survive unless a hard conflict splits them.
4. Score pairs → `stitch_scores` (all pairs, including non-edges, for non-merge diagnosis).
5. Cluster (components → BFS partition → conflict-aware union-find) → `stitch_clusters`.
6. Stable IDs vs the current `id_ledger` → SCD2 ledger update, change feeds, jitter report.
7. Metrics JSON on `stitch_runs` (match rate, category counts, cluster-size distribution, split components, timings).

## Storage notes

DuckDB file under `.aurora/`. DDL is Snowflake-leaning (VARCHAR(n), TIMESTAMP, DOUBLE, BOOLEAN, JSON-as-VARCHAR)
so the same tables can be created in Snowflake with minimal edits (VARIANT for JSON columns, `QUALIFY` is
supported by both). SCD2 tables: `id_ledger`, `gold_merged_customers`. Point-in-time helpers:
`storage/duck.py::ledger_as_of`, `merged_customers_as_of`.
