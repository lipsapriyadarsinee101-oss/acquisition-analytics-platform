# Predictive extension validation
Date: 2026-09-30

- Nine focused unittest tests passed locally.
- The CLI successfully consumed preview/report.json and wrote a separate JSON forecast.
- Tests cover trend fitting, baseline selection, chronological leakage prevention, short history, missing/stale months, invalid monetary values, duplicate keys, source lineage, failed/non-synthetic runs, partial-month exclusion and future periods.
- Existing finance SQL and pipeline code are unchanged.
- The original pipeline suite was not rerun locally because DuckDB was unavailable. GitHub CI installs the declared dependencies and runs the combined suite.
- No Fabric deployment, live vendor connector or LLM was exercised.
- Model selection MAE is diagnostic; it is not independent test accuracy. Synthetic performance does not establish business value.
