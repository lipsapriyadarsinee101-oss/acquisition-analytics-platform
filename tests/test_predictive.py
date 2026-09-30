import copy
import unittest
from portfolio_analytics.predictive import build, forecast, month_index

class PredictiveTests(unittest.TestCase):
    def rows(self, values):
        return [{"company":"A", "period":f"2026-{i+1:02d}", "external_revenue_cents":v}
                for i,v in enumerate(values)]

    def test_linear_trend_beats_naive(self):
        result=forecast(self.rows([100,200,300,400,500,600]), month_index("2026-06"))
        self.assertEqual(result["forecast_external_revenue_cents"],700)
        self.assertEqual(result["validation_mae_cents"]["linear_trend"],0)
        self.assertEqual(result["selected_model"],"linear_trend")

    def test_ties_use_baseline(self):
        self.assertEqual(forecast(self.rows([100]*6),month_index("2026-06"))["selected_model"],
                         "last_month_baseline")

    def test_validation_does_not_train_on_future(self):
        a=forecast(self.rows([100,200,300,400,500,600]),month_index("2026-06"))
        b=forecast(self.rows([100,200,300,400,500,9000]),month_index("2026-06"))
        self.assertEqual(a["validation_folds"][-1]["linear_cents"],
                         b["validation_folds"][-1]["linear_cents"])

    def test_short_acquisition_history_is_not_forecast(self):
        self.assertEqual(forecast(self.rows([1,2,3]),month_index("2026-03"))["status"],
                         "insufficient_history")

    def test_missing_month_and_stale_history(self):
        rows=self.rows([1,2,3,4,5,6,7])
        rows.pop(3)
        self.assertEqual(forecast(rows,month_index("2026-07"))["status"],"incomplete_history")
        self.assertEqual(forecast(self.rows([1]*6),month_index("2026-07"))["status"],"incomplete_history")

    def test_invalid_values_and_duplicate_keys(self):
        for value in [None, float("nan"), True, "100"]:
            with self.assertRaises(ValueError):
                forecast(self.rows([value]*6),month_index("2026-06"))
        rows=self.rows([100]*6)
        with self.assertRaises(ValueError):
            forecast(rows+[rows[0]],month_index("2026-06"))

    def report(self):
        return {"manifest":{"status":"success","synthetic_demo":True,"as_of":"2026-06-30","run_id":"test"},
                "companies":[{"id":"A"},{"id":"NEW"}], "company_monthly":self.rows([100]*6)}

    def test_lineage_and_unobserved_company(self):
        result=build(self.report())
        self.assertEqual(result["source_run_id"],"test")
        self.assertEqual(result["forecasts"][1]["status"],"insufficient_history")
        self.assertFalse(result["ai_usage"]["llm_connected"])

    def test_failed_and_nonsynthetic_runs_rejected(self):
        for field,value in [("status","failed"),("synthetic_demo",False)]:
            report=self.report()
            report["manifest"][field]=value
            with self.assertRaises(ValueError):build(report)

    def test_partial_month_excluded_and_future_rejected(self):
        report=self.report()
        report["manifest"]["as_of"]="2026-06-15"
        result=build(report)
        self.assertEqual(result["training_cutoff"],"2026-05")
        self.assertEqual(result["forecasts"][0]["observations"],5)
        report["company_monthly"][0]["period"]="2027-01"
        with self.assertRaises(ValueError):build(report)
