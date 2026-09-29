# Validation record

Validated locally on 29 September 2026 using Python 3.12, DuckDB 1.4.4 and openpyxl 3.1.5.

- 14 automated tests passed: full reconciliation, acquisition cutoff, intercompany exclusion, immutable raw copy, idempotent reruns, source deletion, invalid account/quarantine, stale data, conflicting duplicates, invalid numeric/hour/FX data, zero denominator, config validation, writer locking and generic HTTP pagination/security.
- End-to-end demonstration: 12 sources, 381 input records, 317 accepted, 63 pre-acquisition exclusions and 1 exact duplicate removed.
- September group external revenue: EUR 353,201.75. Operating earnings proxy: EUR 105,960.53.
- Browser verification: report renders at narrow and desktop widths; switching September to June changes scope from three companies to two and updates KPI/table values.
- Browser download-event capture timed out in the in-app browser; export completion was not verified there. Standard CSV files are included in preview/ as an alternative.
- Docker image and GitHub Actions are supplied but were not executed on Docker/GitHub infrastructure here.
- Fabric bridge code has not been executed in Microsoft Fabric. It must be validated in a non-production workspace before use.

Re-run tests with `python -m unittest discover -s tests -v`. Financial figures are synthetic examples, not business outcomes.
