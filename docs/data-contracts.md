# Input and output contracts

Each source is a full authoritative snapshot for the reporting horizon. Stable business IDs are required. Canonical identifiers are unique by company and fact kind across sources. Identical duplicates are counted and skipped; conflicting duplicates block publication.

| Kind | Required fields | Business key |
|---|---|---|
| ledger | entry_id, date, account, amount, currency; optional counterparty defaults to EXTERNAL | company + entry_id |
| crm | deal_id, date, stage, amount, currency | company + deal_id |
| time | entry_id, date, hours, billable_hours | company + entry_id |
| budget | period, revenue_eur | company + period |

`date`: ISO date `YYYY-MM-DD`; `period`: `YYYY-MM`. One time record is an employee/resource monthly total; each must be between 0 and 744 hours, with billable <= logged. No personal employee data is needed. CRM amounts and budgets must be nonnegative. Financial reversals may be negative. NaN and infinity are invalid.

Config properties:

- `companies`: unique ID, display name, country, local currency, ISO acquisition date.
- `accounts`: company → local account code → canonical category.
- `fx`: month → currency → positive EUR-per-local rate; EUR always equals 1.
- `sources`: unique safe ID, company, kind, format, path or URL, snapshot_as_of, max_age_days and min_rows.
- `columns` (optional per source): canonical name → source column, e.g. `{ "entry_id": "VoucherID", "date": "PostingDate", "account": "AccountCode", "amount": "Value", "currency": "Currency", "counterparty": "Counterparty" }`. Include every required canonical field when using a map.
- `stage_probabilities`: accepted stage labels and weights from 0 to 1. `won` and `lost` must be zero.

CSV files use UTF-8 with optional BOM. JSON file snapshots contain a list of objects. Excel defaults to the `Data` sheet and uses the first row as headers. Supply literal values or cached formula results; openpyxl does not calculate formulas. Dates should be ISO text in source exports. Generic API responses use `items` and same-origin absolute `next` URLs; no vendor-specific authorization flow is supplied.

## Physical output

```
lakehouse/
  latest.json                     # atomically replaced only after success
  runs/<timestamp-unique-id>/
    bronze/                       # original local files; extracted JSON for APIs
    silver/*.parquet              # canonical EUR cents and minute values
    gold/*.parquet                # company/month and group/month data products
    warehouse.duckdb              # isolated per-run SQL database
    config_snapshot.json          # configuration used by this run; no secrets
    gold.sql                      # exact metric implementation used
    manifest.json                 # status, counts, hashes, warnings, reconciliation
    quarantine.json               # rejected record + reason + source row number
    report.json                   # gold outputs + metadata
    ai_context.json               # constrained factual export for future AI consumers
    dashboard.html                # standalone view of the same report.json
```

Silver rows retain `source_id`, `company` and `record_id`. Follow `source_id` to the run's source manifest and bronze hash. Config and SQL hashes identify transformation inputs. This is file-level provenance; it is not a distributed tracing system.

A source `snapshot_as_of` is an asserted export watermark relative to the requested report date, not the file modification time. The historical demo is deliberately evaluated as of 2026-09-30.
