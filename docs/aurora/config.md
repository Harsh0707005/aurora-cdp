# Configuration

`aurora/config/defaults.yaml` → overlaid by `configs/tenants/<tenant>.yaml` →
overlaid by programmatic overrides, validated by `aurora.config.schema.TenantConfig`.

```yaml
tenant: demo
sources: [web, store, loyalty]

blocking:
  max_pairs: 5000000                 # absolute cap on candidate pairs per run
  strategies:                        # kinds: email_exact, email_canonical, name_prefix, phone_e164,
    - {name: email_exact, kind: email_exact, enabled: true, max_block_size: 50}   # phone_prefix, address, fk
    - {name: fk_loyalty,  kind: fk, params: {column: loyalty_id, namespace: loyalty}}
    # register your own kind with aurora.blocking.strategies.register_strategy(kind, fn)

blocklist:                           # stripped before blocking; row gets has_blv=true
  emails: [test@test.com]
  phones: ["0000000000"]
  names: [test, unknown]
  email_domains: [example.invalid]

scoring:
  mode: config                       # config | learned (needs model_path from fit_learned)
  bias: 0.0
  weights: {email_exact: 3.2, surname_jw: 1.6, dob_conflict: -2.0, ...}
  thresholds: [1.0, 2.0, 3.0, 4.0, 5.0]   # five increasing cut points -> categories 0..5
  edge_keep_threshold: 3.0
  deterministic_keys: [email_exact, phone_exact, fk_match]   # -> category 5 "exact"
  hard_conflicts: {dob_conflict: true, given_conflict: true} # -> capped at category 2, never an edge

hygiene:
  supersized_threshold: 64           # components above this get carved / flagged
  hard_limit: 500                    # above this, weakest bridges are cut
  weak_bridge_score: 3.5             # edges below this are removed inside supersized components
  max_carve_iterations: 5

stable_id:
  hungarian_max_nodes: 2000          # bigger bipartite blocks use greedy matching
  namespace: aurora-cdp              # UUIDv5 namespace for aurora_id

storage: {format: delta, lake_root: data/lake, cdc_root: data/cdc, raw_root: data/raw, eval_root: data/eval}
spark:   {master: "local[*]", shuffle_partitions: 16, driver_memory: 4g, extra: {}}
nicknames: {bill: william, bob: robert, ...}   # applied to given names before name blocking / nickname feature
```

Environment: `AURORA_CONFIG` (API config path), `AURORA_SPARK_MASTER`
(overrides `spark.master`, e.g. `spark://spark:7077`).

## Pairwise features

`email_exact, email_sim, phone_exact, phone_prefix, given_jw, surname_jw,
name_exact, nickname_match, postal_eq, house_eq, street_sim, dob_eq, dob_near,
fk_match, name_conflict, given_conflict, dob_conflict` — all in [0, 1]; computed in
`aurora/features/pairwise.py`.
