# large tier at HEAD `8b50675` (stopped after window 1)

First 1M attempt on the AWS box (r6a.4xlarge) with the engine as committed this morning. Stopped deliberately after
window 1 once the quadratic `coverage_stats` query had been identified locally; `window_0.json` / `window_1.json` are the
harness checkpoints (engine timings: blocking 203.5 s at 167k records, 984.2 s at 333k). Superseded by `large`,
`large-fullpairs` and `large-v2`.
