-- Sole executable definition of reporting KPIs; no dashboard recomputation.
-- EUR cents remain integers through aggregation; ratios use NULL for zero denominators.
CREATE OR REPLACE TABLE gold.finance_monthly AS
WITH f AS (
 SELECT company, period,
   SUM(CASE WHEN category='revenue' THEN amount_eur_cents ELSE 0 END) AS revenue_cents,
   SUM(CASE WHEN category='cogs' THEN amount_eur_cents ELSE 0 END) AS cogs_cents,
   SUM(CASE WHEN category='opex' THEN amount_eur_cents ELSE 0 END) AS opex_cents,
   SUM(CASE WHEN category='revenue' AND NOT intercompany THEN amount_eur_cents ELSE 0 END) AS external_revenue_cents,
   SUM(CASE WHEN category='cogs' AND NOT intercompany THEN amount_eur_cents ELSE 0 END) AS external_cogs_cents,
   SUM(CASE WHEN category='opex' AND NOT intercompany THEN amount_eur_cents ELSE 0 END) AS external_opex_cents
 FROM silver.ledger GROUP BY company,period
), b AS (SELECT company,period,SUM(revenue_eur_cents) budget_revenue_cents FROM silver.budget GROUP BY company,period),
c AS (SELECT company,period,SUM(weighted_eur_cents) weighted_pipeline_cents FROM silver.crm GROUP BY company,period),
t AS (SELECT company,period,SUM(minutes) logged_minutes,SUM(billable_minutes) billable_minutes FROM silver.time_entries GROUP BY company,period),
keys AS (SELECT company,period FROM f UNION SELECT company,period FROM b UNION SELECT company,period FROM c UNION SELECT company,period FROM t)
SELECT keys.company, keys.period,
 COALESCE(f.revenue_cents,0) revenue_cents, COALESCE(f.cogs_cents,0) cogs_cents, COALESCE(f.opex_cents,0) opex_cents,
 COALESCE(f.revenue_cents-f.cogs_cents-f.opex_cents,0) operating_earnings_cents,
 COALESCE(f.external_revenue_cents,0) external_revenue_cents,
 COALESCE(f.external_cogs_cents,0) external_cogs_cents,
 COALESCE(f.external_opex_cents,0) external_opex_cents,
 COALESCE(b.budget_revenue_cents,0) budget_revenue_cents,
 COALESCE(c.weighted_pipeline_cents,0) weighted_pipeline_cents,
 COALESCE(t.logged_minutes,0) logged_minutes, COALESCE(t.billable_minutes,0) billable_minutes,
 t.billable_minutes*1.0/NULLIF(t.logged_minutes,0) billable_share,
 (f.external_revenue_cents-b.budget_revenue_cents)*1.0/NULLIF(b.budget_revenue_cents,0) revenue_budget_variance
FROM keys LEFT JOIN f USING(company,period) LEFT JOIN b USING(company,period)
LEFT JOIN c USING(company,period) LEFT JOIN t USING(company,period);

CREATE OR REPLACE TABLE gold.group_monthly AS
SELECT period,
 SUM(external_revenue_cents) revenue_cents,
 SUM(external_cogs_cents) cogs_cents, SUM(external_opex_cents) opex_cents,
 SUM(external_revenue_cents-external_cogs_cents-external_opex_cents) operating_earnings_cents,
 SUM(budget_revenue_cents) budget_revenue_cents,
 SUM(weighted_pipeline_cents) weighted_pipeline_cents,
 SUM(logged_minutes) logged_minutes, SUM(billable_minutes) billable_minutes,
 SUM(billable_minutes)*1.0/NULLIF(SUM(logged_minutes),0) billable_share,
 SUM(external_revenue_cents-external_cogs_cents-external_opex_cents)*1.0/NULLIF(SUM(external_revenue_cents),0) operating_margin,
 (SUM(external_revenue_cents)-SUM(budget_revenue_cents))*1.0/NULLIF(SUM(budget_revenue_cents),0) revenue_budget_variance
FROM gold.finance_monthly GROUP BY period;
