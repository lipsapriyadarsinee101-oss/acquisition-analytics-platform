# Metric contract v1.0.0

## Scope and accounting assumptions

All sample businesses and values are synthetic. Reporting currency is EUR. `period` is `YYYY-MM`.
Actual financial entries are included from each company's `acquired_on` date; CRM dates represent expected-close dates; time dates represent the logged reporting period. Revenue budgets include the whole acquisition month (no daily proration). To support actual mid-month acquisitions, Finance must approve or supply a prorated budget.

Local amounts use a normalized convention: revenues are positive, costs are positive, and negative amounts reverse a previous category posting. This is not a debit/credit general ledger. Transform raw debit/credit exports to this convention before loading. All accounts must map to revenue, cogs or opex; unsupported accounts are rejected rather than silently ignored.

Monthly FX values mean EUR per one local-currency unit. The demo supports EUR, GBP and PLN (two-decimal currencies). Convert and round each row once, HALF_UP to EUR cents, then aggregate. There can be a one-cent difference versus converting an aggregated percentage. No interpolation or silent fallback for missing rates.

## Definitions (implemented only in sql/gold.sql)

| Metric | Definition | Important boundary |
|---|---|---|
| Entity revenue | Sum mapped revenue in EUR cents | Includes group-internal sales |
| External revenue | Revenue excluding counterparties already in acquisition scope on the entry date | Assumes external vs group counterparties are reliably tagged |
| Group revenue | Sum company external revenue | No join to transaction-level CRM/time data |
| Operating earnings proxy | Revenue - mapped cogs - mapped opex | Entity values include internal transactions; group values exclude them. Not certified EBITDA |
| Operating margin | Group operating earnings proxy / group external revenue | Null when revenue is zero |
| Revenue budget variance | (External revenue - EUR revenue budget) / revenue budget | Null when budget is zero; budgets are for external revenue |
| Weighted open pipeline | Sum opportunity EUR value × configured stage probability | Rounded per opportunity to cents; won and lost excluded by zero probability |
| Billable share | Sum billable minutes / sum logged minutes | Hours-weighted, not average of company percentages; not staff-capacity utilization |

These actuals and KPI calculations do not use forecasts or ML models. Stage probabilities are assumptions, not trained estimates. The optional `portfolio_analytics.predictive` module writes separate experimental company forecasts; it does not change Gold metrics. See [My approach](my-approach.md).

## Data products

`gold.finance_monthly`: one row per `(company, period)` present in any of the four fact datasets. Entity-level figures plus external figures and operational measures. Fact domains are aggregated separately and joined only at company-month grain, preventing many-to-many fanout.

`gold.group_monthly`: one row per period, post-acquisition scope and intercompany exclusions. Do not interpret July's scope increase as organic growth.

`ai_context.json`: the same group results plus synthetic marker, run ID, reporting date, currency and metric-contract reference. It is a factual input for future assistants, not an implemented agent or financial recommendation service.

## Quality and ownership

- Finance owns account mapping, budgets, FX, KPI sign-off and consolidation scope.
- Sales Operations owns opportunity stage definitions and probability assumptions.
- Operations owns time coding and billable/non-billable classification.
- Analytics Engineering owns contracts, tests, lineage, release and reconciliation.

Raw source snapshots, configuration hash, exact SQL and source hashes are retained per run. The independent reconciliation compares group revenue with the canonical external ledger. Intercompany revenue and expense must balance by month within one cent. This is a simplified check, not counterparty invoice matching.

Missing whole months are not currently a separate completeness gate; minimum source row count and source freshness are enforced. Real adoption should add expected company-period coverage and ledger control totals before certification.
