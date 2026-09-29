# Microsoft Fabric adaptation

**Status: provided for adaptation; not executed against a Fabric tenant.**

The tested implementation is local DuckDB/Parquet. The supplied notebook bridges an accepted local snapshot to versioned Delta tables, then recomputes the same gold SQL definitions with Spark. This is an initial cloud migration exercise, not a production Fabric solution or an automated tenant deployment.

## Map local components to Fabric

| Local demonstration | Target Fabric component |
|---|---|
| CSV/JSON/Excel/API extracts | Data Factory Copy activities / Dataflow Gen2 / connector-specific ingestion |
| Bronze raw snapshots | Immutable run-partitioned Files in a bronze lakehouse |
| Silver Parquet facts | Validated Delta tables in a silver lakehouse |
| Gold SQL products | Curated Delta tables / SQL analytics endpoint |
| Dashboard / JSON | Power BI semantic model, controlled data exports and AI consumers |
| CLI dependencies | Scheduled Data Factory pipeline with validation gates |
| Run manifests | Run audit table, monitoring and configured alert delivery |
| GitHub Actions validation | Git-connected development workspace plus reviewed deployment promotion |

## Try the bridge notebook

1. Run the local demo and identify the run in `lakehouse/latest.json`.
2. Create a **non-production** Fabric lakehouse and attach it to a Python notebook.
3. Upload the accepted run's `silver/`, `gold.sql`, `manifest.json` and `config_snapshot.json` to `Files/acquisition-demo/<run_id>/`.
4. Paste/import `publish_snapshot.py` into that notebook, set `RUN_ID`, and run with an attached Spark session.
5. The notebook rejects failed manifests, checks imported record counts, creates versioned silver Delta tables, recalculates gold views and checks the group revenue total before writing versioned gold tables.
6. Inspect those tables and compare results with the local report. Do not point a live semantic model to them until separately approved.

The bridge reuses locally validated silver data: it does **not** reimplement all Python bronze-to-silver validation as distributed Spark processing. For a fully native deployment, port those contracts and tests, then use native source activities and authoritative source watermarks.

## Native orchestration blueprint

`Extract all required source snapshots → Validate contracts/coverage/FX/mappings → Canonical silver → Gold SQL → Reconcile to source controls → Approve/publish semantic-model version → Refresh report → Alert on failure`.

Use versioned outputs or another reviewed publication design. A multi-table Spark write is not one atomic transaction. The bridge intentionally creates versioned tables and does not replace a shared `latest` view automatically.

## Development and release

- Create separate development, test and production workspaces with named owners and least-privilege access.
- Connect development to Git using the supported Fabric integration for your tenant/provider.
- Create actual lakehouse, notebook and pipeline items in Fabric, then commit the platform-generated item definitions; do not invent item IDs in this repository.
- External connection credentials and secrets belong in the environment, not source control.
- Promote reviewed items through deployment pipelines; verify environment-specific connections, lakehouse bindings and schedules after promotion.
- Git tracks lakehouse metadata, not the table/file data itself. Provide separate data ingestion, backup and recovery arrangements.
- Define access boundaries for finance vs operating-company users before exposing gold tables. No production access-control implementation is supplied here.

## Primary references (reviewed 29 September 2026)

- [Microsoft: medallion architecture for Fabric](https://learn.microsoft.com/en-us/fabric/onelake/onelake-medallion-lakehouse-architecture)
- [Microsoft: lakehouse Git integration and deployment pipelines](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-git-deployment-pipelines)

These guides informed the layer/deployment mapping. Tenant configuration, capacity and supported item behavior must be checked in your own environment.
