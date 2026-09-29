# Interview notes

## 60-second explanation

“I built a portfolio project for the reporting challenges of an acquisition-led company. It combines synthetic accounting, CRM, time-tracking and Excel budget data from three businesses into one reporting model.

The pipeline keeps raw inputs, validates and standardizes the data, maps different account codes, converts currencies and applies acquisition dates. A shared SQL layer calculates financial and operational measures so the dashboard and other consumers use the same definitions.

I also added reconciliation, failure logs, automated tests and a last-good publication mechanism. If a source fails validation, it cannot replace the accepted report.

The working version runs locally with Python, DuckDB and Parquet. I included a Microsoft Fabric adaptation notebook and deployment guide, but I have not claimed a live Fabric deployment.”

## Five-minute demonstration

1. Explain the business problem and show the synthetic label.
2. Compare June with July and explain Cedar's acquisition cutoff.
3. Explain account mapping and GBP/PLN to EUR conversion.
4. Show September entity vs external revenue and the €800 internal transaction.
5. Show source counts, duplicate warning and independent reconciliation.
6. Show one failing test scenario and how the previous publication survives.
7. Show the shared SQL metric contract and how another acquisition is configured.

## Design decisions you should understand

- Why full snapshot? Clear correction/deletion behavior and fewer hidden state problems at demo scale. CDC becomes useful with larger sources and reliable change watermarks.
- Why DuckDB/Parquet? Easy local execution, portable columnar outputs and SQL analysis. This is not evidence that a Microsoft Fabric production tenant was operated.
- Why monetary integers? Explicit conversion and rounding, then exact additive aggregation.
- Why aggregate before joins? Joining ledger lines directly to CRM/time records can multiply balances.
- Why last-good publication? Users keep access to accepted data while an upstream problem is fixed; operations still see the failed attempt.
- Why an earnings proxy? Only revenue/direct/operating cost categories are present. It is not justified to call it audited EBITDA or statutory consolidation.

## Honest CV bullet

Built a synthetic acquisition analytics platform integrating CSV, JSON, Excel and a generic API connector, with layered Parquet outputs, acquisition-aware finance metrics, data-quality gates, automated tests and an interactive dashboard; documented an adaptation path to Microsoft Fabric.

Do not claim measured cost savings, client deployments, finance employment, live vendor integration or production Fabric experience from this project alone.
