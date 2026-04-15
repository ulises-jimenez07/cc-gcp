-- Tutorial 2.2: Create a partitioned and clustered BigQuery table
-- from the Chicago taxi public dataset.
--
-- Partitioned by DATE(trip_start_timestamp) → prune entire date ranges
-- Clustered by pickup_community_area, payment_type → prune blocks within a partition
--
-- Run in BigQuery Console or via:
--   bq query --use_legacy_sql=false < create_optimized_table.sql

CREATE OR REPLACE TABLE `retail_analytics.optimized_taxi_trips`
PARTITION BY DATE(trip_start_timestamp)
CLUSTER BY pickup_community_area, payment_type
OPTIONS (
  description = 'Chicago taxi trips partitioned by date, clustered by area and payment type',
  partition_expiration_days = 365
)
AS
SELECT
  unique_key,
  taxi_id,
  trip_start_timestamp,
  trip_end_timestamp,
  CAST(trip_seconds  AS INT64)   AS trip_seconds,
  CAST(trip_miles    AS FLOAT64) AS trip_miles,
  CAST(pickup_community_area  AS INT64) AS pickup_community_area,
  CAST(dropoff_community_area AS INT64) AS dropoff_community_area,
  CAST(fare     AS FLOAT64) AS fare,
  CAST(tips     AS FLOAT64) AS tips,
  CAST(tolls    AS FLOAT64) AS tolls,
  CAST(extras   AS FLOAT64) AS extras,
  CAST(trip_total AS FLOAT64) AS trip_total,
  payment_type,
  company
FROM `bigquery-public-data.chicago_taxi_trips.taxi_trips`
WHERE
  trip_start_timestamp > '2023-01-01'
  AND trip_seconds > 0
  AND trip_miles > 0
  AND fare > 0;
