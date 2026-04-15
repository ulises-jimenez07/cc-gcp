-- Tutorial 3.1: Bronze / Silver / Gold data warehouse layers
-- Run each block separately in the BigQuery Console.

-- ============================================================
-- SILVER: Cleaning View on top of the raw Bronze table
-- ============================================================
CREATE OR REPLACE VIEW `retail_analytics.clean_sales` AS
SELECT
  PARSE_DATE('%Y-%m-%d', date)  AS sale_date,
  TRIM(LOWER(store_id))         AS store_id,
  TRIM(LOWER(product))          AS product,
  TRIM(LOWER(category))         AS category,
  CAST(quantity  AS INT64)      AS quantity,
  CAST(unit_price AS FLOAT64)   AS unit_price,
  CAST(revenue   AS FLOAT64)    AS revenue
FROM `retail_analytics.raw_sales`
WHERE
  date       IS NOT NULL
  AND quantity  IS NOT NULL
  AND revenue   IS NOT NULL
  AND SAFE_CAST(revenue  AS FLOAT64) > 0
  AND SAFE_CAST(quantity AS INT64)   > 0;


-- ============================================================
-- GOLD: Materialized View — pre-aggregated daily metrics
-- BigQuery refreshes this automatically when the base data changes.
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS `retail_analytics.daily_revenue_by_store`
OPTIONS (
  enable_refresh = true,
  refresh_interval_minutes = 60
)
AS
SELECT
  sale_date,
  store_id,
  category,
  SUM(quantity)   AS total_units,
  SUM(revenue)    AS total_revenue,
  COUNT(*)        AS transaction_count,
  AVG(unit_price) AS avg_unit_price
FROM `retail_analytics.clean_sales`
GROUP BY sale_date, store_id, category;


-- ============================================================
-- REPORT: Scheduled Query target — monthly KPI summary
-- Set up as a Scheduled Query in the BigQuery Console or via bq CLI.
-- ============================================================
SELECT
  DATE_TRUNC(sale_date, MONTH)  AS month,
  store_id,
  SUM(total_revenue)            AS monthly_revenue,
  SUM(total_units)              AS monthly_units,
  SUM(transaction_count)        AS monthly_transactions,
  ROUND(AVG(avg_unit_price), 2) AS overall_avg_price
FROM `retail_analytics.daily_revenue_by_store`
GROUP BY month, store_id
ORDER BY month DESC, monthly_revenue DESC;
