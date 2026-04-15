-- Tutorial 3.2: BigQuery ML — train and evaluate models in SQL

-- ============================================================
-- Step 1: Create training dataset
-- ============================================================
CREATE OR REPLACE TABLE `retail_analytics.taxi_training_data` AS
SELECT
  CAST(trip_miles AS FLOAT64)                         AS trip_miles,
  IFNULL(CAST(pickup_community_area  AS INT64), 0)    AS pickup_area,
  IFNULL(CAST(dropoff_community_area AS INT64), 0)    AS dropoff_area,
  CAST(fare AS FLOAT64)                               AS fare,
  CASE payment_type
    WHEN 'Credit Card' THEN 1
    WHEN 'Cash'        THEN 2
    ELSE 0
  END                                                 AS payment_type_encoded,
  CAST(trip_seconds AS INT64)                         AS label   -- target variable
FROM `bigquery-public-data.chicago_taxi_trips.taxi_trips`
WHERE
  trip_start_timestamp BETWEEN '2023-01-01' AND '2023-12-31'
  AND trip_seconds  BETWEEN 60   AND 7200   -- 1 min to 2 hours
  AND trip_miles    BETWEEN 0.1  AND 50
  AND fare          BETWEEN 2.5  AND 200;


-- ============================================================
-- Step 2: Train a Linear Regression model
-- ============================================================
CREATE OR REPLACE MODEL `retail_analytics.trip_duration_model`
OPTIONS (
  model_type        = 'linear_reg',
  input_label_cols  = ['label'],
  data_split_method = 'auto_split',   -- 80/20 train/test split
  max_iterations    = 20
) AS
SELECT
  trip_miles,
  pickup_area,
  dropoff_area,
  fare,
  payment_type_encoded,
  label
FROM `retail_analytics.taxi_training_data`;


-- ============================================================
-- Step 3: Evaluate model performance
-- ============================================================
SELECT *
FROM ML.EVALUATE(
  MODEL `retail_analytics.trip_duration_model`,
  (
    SELECT trip_miles, pickup_area, dropoff_area, fare, payment_type_encoded, label
    FROM `retail_analytics.taxi_training_data`
  )
);


-- ============================================================
-- Step 4: Feature importance (weights)
-- ============================================================
SELECT
  processed_input AS feature,
  ROUND(weight, 4) AS weight
FROM ML.WEIGHTS(MODEL `retail_analytics.trip_duration_model`)
ORDER BY ABS(weight) DESC;


-- ============================================================
-- Step 5: Generate predictions on new data
-- ============================================================
SELECT
  trip_miles,
  fare,
  ROUND(predicted_label, 0)      AS predicted_seconds,
  ROUND(predicted_label / 60, 1) AS predicted_minutes
FROM ML.PREDICT(
  MODEL `retail_analytics.trip_duration_model`,
  (
    SELECT 2.5 AS trip_miles, 1 AS pickup_area, 8  AS dropoff_area, 12.50 AS fare, 1 AS payment_type_encoded
    UNION ALL
    SELECT 8.0,               6,                22,                 28.00,          2
    UNION ALL
    SELECT 0.8,               32,               32,                 5.50,           1
    UNION ALL
    SELECT 15.0,              10,               5,                  45.00,          1
  )
);


-- ============================================================
-- Step 6: ARIMA+ time-series model for revenue forecasting
-- ============================================================
CREATE OR REPLACE MODEL `retail_analytics.revenue_forecast`
OPTIONS (
  model_type                  = 'arima_plus',
  time_series_timestamp_col   = 'sale_date',
  time_series_data_col        = 'daily_revenue',
  auto_arima                  = TRUE,
  data_frequency              = 'DAILY',
  decompose_time_series       = TRUE,
  holiday_region              = 'US'
) AS
SELECT
  sale_date,
  SUM(total_revenue) AS daily_revenue
FROM `retail_analytics.daily_revenue_by_store`
GROUP BY sale_date
HAVING daily_revenue > 0
ORDER BY sale_date;


-- ============================================================
-- Step 7: 30-day forecast with confidence intervals
-- ============================================================
SELECT
  forecast_timestamp,
  ROUND(forecast_value, 2)                    AS predicted_revenue,
  ROUND(prediction_interval_lower_bound, 2)   AS lower_bound,
  ROUND(prediction_interval_upper_bound, 2)   AS upper_bound
FROM ML.FORECAST(
  MODEL `retail_analytics.revenue_forecast`,
  STRUCT(30 AS horizon, 0.9 AS confidence_level)
)
ORDER BY forecast_timestamp;
