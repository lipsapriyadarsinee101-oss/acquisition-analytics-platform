# Onboarding a newly acquired company

## 1. Agree the reporting boundary

Record acquisition date, legal entity ID, local currency, source owners and reporting calendar. Agree whether partial acquisition months require budget proration. Collect control totals from Finance before implementing a connector.

## 2. Inventory sources

Identify ERP/accounting postings, CRM opportunity snapshots, time-system monthly totals and budget workbooks. Confirm stable IDs, sign conventions, export schedules, corrections/deletions, permissions and expected row counts. Use read-only service accounts and secrets from the target environment.

## 3. Extend the generated configuration

Add a company entry, map each local account to the canonical model, add monthly FX rates and supply four source configurations. Source-specific column maps let you reuse connectors without rewriting metrics.

Example company:

```json
{"id":"DEL","name":"Delta Services (synthetic)","country":"Germany","currency":"EUR","acquired_on":"2026-09-01"}
```

Example source:

```json
{"id":"del_ledger","company":"DEL","kind":"ledger","format":"csv","path":"data/del_ledger.csv","snapshot_as_of":"2026-09-30","max_age_days":7,"min_rows":1}
```

Also add `del_crm`, `del_time` and `del_budget`. Extend `accounts.DEL` and currency rates as required. The runtime requires all four domains for every company; use explicit zero budget/time rows when appropriate rather than silently omitting a domain.

## 4. Reconcile before publication

Run a separate copy using `--project` to keep the last accepted production snapshot untouched. Compare revenue and costs against the source trial balance/export, check currency conversion and acquisition cutoffs, resolve quarantine, and verify intercompany matching. Review absent company-months and source completeness manually in this version.

## 5. Obtain business sign-off

Finance signs off balances, scope and definitions; Operations verifies time figures; Sales confirms opportunity stages. Document differences and accepted limitations. Provide a sample dashboard and explain the definitions in everyday language.

## 6. Operate

Schedule extraction only after upstream completion. Define source deadlines, named owners, incident escalation and a recovery process. For this local demo, use the CLI and a system scheduler. For Fabric, use a Data Factory pipeline to sequence source refresh, notebook execution and quality-gated promotion.
