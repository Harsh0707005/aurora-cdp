# Architecture

```
raw parquet ──► preprocess (standardise, blocklist) ──► blocking (DNF keys, size guard)
     │                                                           │
     │                                   candidate pairs (rid_l < rid_r, strategies)
     │                                                           ▼
     │                 pairwise features (rapidfuzz) ──► ordinal scorer (config | learned)
     │                                                           │  Stitch_Scores (all pairs)
     │                                            edges: score ≥ keep & not hard_conflict
     │                                                           ▼  (collected to driver)
     │                        union-find ──► hygiene (carve supersized, cut weak bridges)
     │                                                           ▼
     │               stable IDs: max-overlap vs previous Unified_Customer (Hungarian / greedy)
     ▼                                                           ▼
Unified_Preprocessed_Raw   Unified_Coalesced / Unified_Customer / Merged_Customers / Customer360
                           Stable_Id_Mapping / Lineage / Unified_Changes_* ──► CDC JSONL (Kafka stub)
                                                           ▼
                                        FastAPI (/profiles, /search, /clusters, /resolve) + HTMX UI
```

Modules (`aurora/`):

- `config/` — Pydantic schema + defaults; `utils/` — standardisation, UUIDv5 ids.
- `synth/` — Faker generator with planted truth, households (hard negatives), drift.
- `blocking/` — key builders, self-join per strategy, block-size guard, diagnostics.
- `features/` — pairwise feature vector; `scoring/` — ordinal scorer, tuner, logistic mode.
- `graph/` — edges, union-find, hygiene, stable-ID matching.
- `pipeline/` — `runner` (one pass), `cdc` (tables, sinks), `eval` (metrics).
- `io/` — Spark session with Delta probe/fallback, Spark-free Delta-log reader, DDL.
- `api/` — FastAPI + Jinja/HTMX explorer.

Scale notes: blocking, features and scoring run as Spark `mapInPandas`; only
kept edges (bounded by `max_block_size` / `max_pairs`) come to the driver. The
final per-row assignment (~rows × 7 columns) also passes through pandas, which
is fine to a few million rows; beyond that, move clustering to GraphFrames or
an iterative Spark label-propagation and keep everything else unchanged.

Reference behaviour (Amperity public docs/patents) is replicated conceptually:
threshold-based ordinal scoring with 0..5 categories, deterministic tie-breaks,
hard-conflict refusal, supersized component carving, and max-overlap stable
IDs with the split-orphans-all-but-one rule and jitter reporting.
