"""Small, dependency-free forecasting experiment on accepted synthetic gold data."""
import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean


def month_index(period):
    if not isinstance(period, str) or not re.fullmatch(r"\d{4}-\d{2}", period):
        raise ValueError("Period must be YYYY-MM")
    dt = date.fromisoformat(period + "-01")
    return dt.year * 12 + dt.month - 1


def period_label(index):
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def trend(values):
    """Ordinary least squares: external revenue = intercept + slope * month."""
    center = (len(values) - 1) / 2
    average = mean(values)
    slope = sum((i-center)*(v-average) for i,v in enumerate(values)) / sum(
        (i-center)**2 for i in range(len(values)))
    return round(average + slope * (len(values)-center))


def forecast(rows, cutoff):
    rows = sorted(rows, key=lambda r: r["period"])
    periods = [month_index(r["period"]) for r in rows]
    values = [r["external_revenue_cents"] for r in rows]
    if any(type(v) is not int for v in values):
        raise ValueError("Revenue must be integer EUR cents")
    if len(periods) != len(set(periods)):
        raise ValueError("Duplicate company-month")
    if periods and periods[-1] > cutoff:
        raise ValueError("Report contains future periods")
    if len(rows) < 6:
        return {"status": "insufficient_history", "observations": len(rows)}
    if periods[-1] != cutoff or any(b-a != 1 for a,b in zip(periods, periods[1:])):
        return {"status": "incomplete_history", "observations": len(rows)}
    # Each validation forecast is trained only on earlier months.
    folds = []
    for stop in range(3, len(values)):
        training = values[:stop]
        folds.append({"period": rows[stop]["period"], "actual_cents": values[stop],
                      "linear_cents": trend(training), "naive_cents": training[-1]})
    linear_mae = mean(abs(f["actual_cents"]-f["linear_cents"]) for f in folds)
    naive_mae = mean(abs(f["actual_cents"]-f["naive_cents"]) for f in folds)
    model = "linear_trend" if linear_mae < naive_mae else "last_month_baseline"
    return {"status": "experimental", "observations": len(rows),
            "target_period": period_label(cutoff+1), "selected_model": model,
            "forecast_external_revenue_cents": trend(values) if model == "linear_trend" else values[-1],
            "validation_mae_cents": {"linear_trend": linear_mae, "last_month_baseline": naive_mae},
            "validation_folds": folds,
            "limitation": "Model selection scores are not an independent final test. No seasonality or uncertainty interval."}


def build(report):
    manifest = report["manifest"]
    if manifest["status"] != "success":
        raise ValueError("Only successful pipeline reports can be used")
    if manifest.get("synthetic_demo") is not True:
        raise ValueError("This experiment is restricted to synthetic demo reports")
    as_of = date.fromisoformat(manifest["as_of"])
    cutoff = month_index(as_of.strftime("%Y-%m"))
    # Exclude a partial month from monthly model training.
    if date.fromordinal(as_of.toordinal()+1).month == as_of.month:
        cutoff -= 1
    groups = defaultdict(list)
    known = {c["id"] for c in report["companies"]}
    for row in report["company_monthly"]:
        if row["company"] not in known:
            raise ValueError("Unknown company")
        period = month_index(row["period"])
        if period > month_index(as_of.strftime("%Y-%m")):
            raise ValueError("Report contains future periods")
        if period <= cutoff:
            groups[row["company"]].append(row)
    forecasts = [{"company": company, **forecast(groups[company], cutoff)} for company in sorted(known)]
    # No group forecast: changing acquisition scope would confound growth.
    return {"synthetic": True, "currency": "EUR", "source_run_id": manifest["run_id"],
            "training_cutoff": period_label(cutoff), "forecasts": forecasts,
            "ai_usage": {"implemented": "Structured, traceable context for a future assistant",
                         "llm_connected": False,
                         "rules": ["Distinguish actuals from forecasts", "Cite the source run and metric",
                                   "Do not infer causes from correlations", "Require human review"]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.report.resolve() == args.output.resolve():
        parser.error("Output must differ from input report")
    raw = args.report.read_bytes()
    result = build(json.loads(raw))
    result["source_report_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
