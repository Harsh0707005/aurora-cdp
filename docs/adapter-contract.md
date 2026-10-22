# Adapter contract for the scoring harness

The scoring harness lives in a separate repository and must be able to run Aurora's identity resolution on a
file and read back an assignment table. Aurora does not ship a competing metrics suite.

## Command

```bash
aurora stitch run --input records.csv --out assignments.csv \
    [--scores-out scores.csv] [--mapping mapping.yaml] [--previous prev_assignments.csv] \
    [--datasource NAME] [--threshold 3.0] [--workspace DIR] [--keep-workspace]
```

Runs a full Stitch pass on the input in a throwaway workspace (no state is shared with `.aurora/` unless
`--workspace` is given) and writes the assignment table. Exit code 0 on success; errors go to stderr.

Equivalent Python entry point: `aurora_cdp.adapter.run_on_file(cfg, input_path, out_path, ...)`.
To export the latest run of an existing workspace instead: `aurora stitch export --out assignments.csv [--scores-out scores.csv] [--run-id ID]`.

## Input

CSV or Parquet, one row per source record. Either:

- **semantic columns already present** — `source_record_id` (or `pk`), optional `datasource`, and any of
  `given_name, surname, email, phone, address, address2, city, state, postal, country, birthdate, loy_id, ck,
  update_dt, fk_<namespace>…`; or
- **`--mapping mapping.yaml`** with the same shape used by pipelines:

```yaml
pk: customer_id
ck: null
fields: {first_name: given_name, last_name: surname, email_address: email, mobile: phone, zip: postal, dob: birthdate}
fk: {loyalty_no: loyalty}
```

If `datasource` is absent every row gets `--datasource` (default `input`). Record ids must be unique per datasource.

## Output: `assignments.csv`

| column | type | meaning |
|---|---|---|
| `source_record_id` | string | the input record id (`pk`) |
| `unified_id` | UUID string | the stable Aurora ID of the record's cluster |
| `run_date` | `YYYY-MM-DD` | date of the run |
| `datasource` | string | source name |
| `pk` | string | same as `source_record_id` (kept for joins with other Aurora tables) |
| `cluster_id` | string | run-local cluster id |
| `run_id` | string | Aurora run id |

Row count equals the number of input records. `--out foo.parquet` writes Parquet instead of CSV.

## Optional: `scores.csv` (pair level)

`left_datasource, left_record_id, right_datasource, right_record_id, score (0–5), match_category
(hard_conflict | non_conflict | weak | moderate | high | excellent | exact), match_type (scored | deterministic |
trivial_duplicate | carried), is_edge (bool)`. Contains every candidate pair that was scored, including non-merges.

## Stability across runs

Pass `--previous assignments_from_last_run.csv` to seed the ID ledger so `unified_id` values are inherited via
the stable-ID algorithm and the run's jitter is reported in the one-line summary. Without it, every run mints
fresh UUIDs (cluster composition is still comparable via `cluster_id`).

## Ground truth

Aurora never reads a truth column; extra input columns (e.g. `truth_id`) are ignored by matching and carried
only in the bronze payload. The harness joins truth to `source_record_id` itself.
