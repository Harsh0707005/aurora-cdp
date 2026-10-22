# External interfaces (stable contract)

This document is the contract other code (notably the scoring/evaluation harness being merged into this repo)
should code against. The two entrypoints below share one implementation and will stay source-compatible;
additive changes only.

## 1. CLI: `aurora resolve`

```bash
aurora resolve --input records.jsonl --output assignments.csv [--config aurora.yaml] \
               [--scores scores.csv] [--previous last_assignments.csv] [--mapping mapping.yaml] \
               [--datasource NAME] [--threshold 3.0]
# equivalent, no console script needed:
python -m aurora_cdp.adapters.resolver --input records.jsonl --output assignments.csv [--config aurora.yaml]
```

- Input formats: `.csv`, `.parquet`, `.jsonl`/`.ndjson`, `.json` (array of objects).
- Output format follows the extension: `.csv`, `.parquet`, `.jsonl`.
- Runs in a temporary workspace; never touches `.aurora/` or any shared state. Exit code 0 on success.
- `--config` is an overlay YAML with the same keys as `aurora_cdp/config/defaults.yaml`
  (e.g. `matcher: {match_threshold: 3.5}`); `--threshold` is a shortcut for that one key.
- Prints one summary line: records, clusters, edges, jitter %, run id, output paths.

(`aurora stitch run --input --out` is an older alias with the same output; prefer `aurora resolve`.)

## 2. Python: `aurora_cdp.adapters.resolve_records`

```python
from aurora_cdp.adapters import resolve_records, resolve_file, ResolveResult

result: ResolveResult = resolve_records(
    records,                 # DataFrame | list[dict] | path (csv/parquet/jsonl/json)
    config=None,             # None | Config | dict overrides | path to aurora.yaml
    previous=None,           # None | DataFrame | path: prior assignments (unified_id + source_record_id[/datasource])
    mapping=None,            # None | dict | path: semantic mapping when columns are raw (see §4)
    datasource="input",      # used when records carry no `datasource` column
    threshold=None,          # override matcher.match_threshold
    workspace=None,          # keep DuckDB state here instead of a temp dir (debugging)
)
result.assignments   # pandas DataFrame, columns in §3
result.scores        # pandas DataFrame, pair-level, columns in §3
result.metrics       # dict (records, pairs_scored, edges, clusters, cluster_size_distribution, jitter{...}, timings_sec, ...)
result.run_id        # str
result.clusters      # dict unified_id -> ["datasource|pk", ...]
result.to_jsonl(path)
```

`resolve_file(input_path, output_path, config=None, scores_path=None, previous=None, mapping=None, datasource="input", threshold=None)`
is the file-in/file-out wrapper used by the CLI.

## 3. Schemas

### Input records
One row per source record.

| column | required | notes |
|---|---|---|
| `source_record_id` (or `pk`) | yes | unique within a datasource |
| `datasource` | no | defaults to `--datasource`; blocking/matching is cross-source |
| `given_name, surname, email, phone, address, address2, city, state, postal, country, birthdate, loy_id, ck, update_dt` | any subset | semantic columns; blanks/NaN = missing |
| `fk_<namespace>` | no | foreign keys to interaction data (become blocking keys / features) |
| anything else (e.g. `truth_id`) | ignored by matching | |

### `assignments` (one row per input record)

| column | type | meaning |
|---|---|---|
| `source_record_id` | str | input id |
| `unified_id` | str (UUID) | stable Aurora ID of the record's cluster |
| `run_date` | `YYYY-MM-DD` | |
| `datasource` | str | |
| `pk` | str | = `source_record_id` |
| `cluster_id` | str | run-local cluster id (16 hex) |
| `run_id` | str | |

### `scores` (one row per scored candidate pair, including non-merges)

`left_datasource, left_record_id, right_datasource, right_record_id, score (float 0–5), match_category
(hard_conflict | non_conflict | weak | moderate | high | excellent | exact), match_type (scored | deterministic |
trivial_duplicate | carried), is_edge (bool; score ≥ threshold and not a hard conflict)`.

### `metrics` (subset guaranteed)

`records, pairs_blocked, pairs_scored, edges, clusters, multi_record_clusters, max_cluster_size,
cluster_size_distribution{"1","2","3-5","6-10","11-50","50+"}, split_components, supersized_components,
skipped_blocks, threshold, jitter{records_total, records_compared, records_changed, jitter_pct, ids_minted,
ids_retired, alert}, timings_sec{load, blocking, scoring, clustering, stable_id, persist}`.

## 4. Mapping file (raw column names → semantics)

```yaml
pk: customer_id          # required
ck: null                 # optional customer key column
fields:                  # raw column -> semantic
  first_name: given_name
  last_name: surname
  email_address: email
  mobile: phone
  zip: postal
  dob: birthdate
  loyalty_no: loy_id
  updated_at: update_dt
fk:                      # raw column -> fk namespace
  pos_customer_no: pos
```

## 5. Stable IDs across calls

Pass `previous=` (the `assignments` of the last call, or any table with `unified_id` and `source_record_id`
[+ `datasource`]) and the run inherits IDs by the documented greedy max-overlap algorithm; `metrics["jitter"]`
then reports `% of shared records whose unified_id changed`, `ids_minted`, `ids_retired`.

## 6. Versioning

Interface version **1** (2026-10-22). Columns may be added, never removed or renamed; new CLI flags are optional.
Breaking changes would ship as `aurora resolve2` / `resolve_records_v2` rather than mutate this contract.
