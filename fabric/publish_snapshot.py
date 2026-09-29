# Paste into a Microsoft Fabric Python notebook with an attached non-production lakehouse.
# ADAPTATION TEMPLATE: this file has not been run in a Fabric workspace.
import json
import re
from pathlib import Path

RUN_ID = "REPLACE_WITH_ACCEPTED_LOCAL_RUN_ID"
if not re.fullmatch(r"[A-Za-z0-9_-]+", RUN_ID) or RUN_ID.startswith("REPLACE"):
    raise ValueError("Set RUN_ID to the uploaded successful snapshot ID")

base = Path(f"/lakehouse/default/Files/acquisition-demo/{RUN_ID}")
manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
if manifest["status"] != "success" or manifest["run_id"] != RUN_ID:
    raise ValueError("Only a matching accepted snapshot may be imported")

suffix = re.sub(r"[^a-zA-Z0-9_]", "_", RUN_ID)
table_map = {"ledger": "ledger", "crm": "crm", "time": "time_entries", "budget": "budget"}
for kind, table in table_map.items():
    # spark is provided by the Fabric notebook runtime.
    frame = spark.read.parquet(f"Files/acquisition-demo/{RUN_ID}/silver/{table}.parquet")
    expected = sum(s["accepted"] for s in manifest["sources"] if s["kind"] == kind)
    if frame.count() != expected:
        raise ValueError(f"Record-count mismatch for {table}")
    # Versioned table names avoid replacing a currently consumed snapshot.
    frame.write.format("delta").mode("errorifexists").saveAsTable(f"silver_{table}_{suffix}")
    frame.createOrReplaceTempView(f"silver_{table}")

sql = (base / "gold.sql").read_text(encoding="utf-8")
# Remove line comments before statement splitting; generated SQL has no quoted semicolons.
sql = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
sql = sql.replace("CREATE OR REPLACE TABLE gold.", "CREATE OR REPLACE TEMP VIEW gold_")
sql = sql.replace("silver.", "silver_").replace("gold.", "gold_")
for statement in sql.split(";"):
    if statement.strip():
        spark.sql(statement)

actual = spark.sql("SELECT COALESCE(SUM(revenue_cents),0) AS value FROM gold_group_monthly").first()["value"]
if int(actual) != int(manifest["reconciliation"]["external_ledger_revenue_cents"]):
    raise ValueError("Fabric gold revenue failed reconciliation; do not publish")
for table in ["finance_monthly", "group_monthly"]:
    spark.table(f"gold_{table}").write.format("delta").mode("errorifexists").saveAsTable(f"gold_{table}_{suffix}")
print(f"Created versioned Delta snapshot {suffix}. Validate all measures before semantic-model promotion.")
