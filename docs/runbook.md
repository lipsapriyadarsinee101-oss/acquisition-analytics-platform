# Operations runbook

## Run / observe

- `python -m portfolio_analytics run`: full snapshot refresh, default historical cutoff 2026-09-30.
- `python -m portfolio_analytics run --as-of YYYY-MM-DD`: explicit reporting cutoff; provide suitable source snapshots and FX.
- `python -m portfolio_analytics status`: latest attempted run, exit 0 on success or 1 on failure.
- `lakehouse/latest.json`: last published successful run, which may differ from the latest attempt.
- `manifest.json`: input, accepted, duplicate, excluded and rejected row counts, quality alerts, reconciliation, times and hashes.

The HTML is a point-in-time artifact. It cannot discover a later failed run without regenerating it. Operations should monitor `status`/manifests rather than treat an old green dashboard as current health. Freshness gates concern source snapshots; the demo does not send email/Slack alerts.

## Failure handling

| Failure | Response |
|---|---|
| Stale snapshot | Ask source owner for a current export; do not relabel old data as fresh |
| Unmapped account / invalid numeric | Inspect quarantine; get Finance-approved mapping or correct the source |
| Conflicting duplicate ID | Fix upstream identity/correction rules; do not arbitrarily pick a row |
| Missing FX | Obtain the approved monthly rate and rerun |
| Unbalanced intercompany | Reconcile matching seller/buyer records and currencies; do not bypass the gate |
| API failure | Check auth environment variable, endpoint contract and upstream availability; bounded retries are built in |
| `pipeline.lock` exists | Check that no process is running; after a confirmed crash, remove only this lock file and rerun |

No failed run changes the last-good pointer. Correct the source/configuration and start a new run; failed and successful run artifacts remain available. Runtime keeps historical files but does not implement automatic retention or backups.

## Reruns, publication and rollback

Full-snapshot rebuilding is idempotent at the business-data level. Run IDs and timestamps intentionally change. All layers live in a new directory; a temporary pointer file is atomically renamed only after the dashboard and report are written. One writer is enforced with an exclusive lock file; not a distributed lock.

For a controlled rollback, stop writers, select a previously accepted run, validate its manifest, and atomically replace `latest.json` with that run's paths. Do not edit the old report or rewrite bronze. A corrected forward run is usually easier to audit.

## Security / production gaps

The public project contains only synthetic data. Bronze and quarantine may contain sensitive records in real use: restrict access, encrypt storage, add retention/deletion policies and prevent these files reaching Git. Offline dashboards and JSON have no built-in authorization.

The generic API connector reads a token from an environment variable and rejects off-origin pagination/redirects. Production should use managed identities or a secret manager, source-specific refresh tokens and structured log redaction.

Before real deployment: add environment isolation, role-based/row-level permissions, source control totals and period coverage, backup/restore, managed alert delivery, monitoring SLAs, approved accounting policies and formal reconciliation ownership.

## Git release workflow

Create a feature branch → modify connector/config/model → run tests → pull request → review metric changes with owner → CI creates synthetic report artifact → inspect and approve → merge. Repository CI is local validation, not an automatic cloud deployment. Fabric promotion is described separately.
