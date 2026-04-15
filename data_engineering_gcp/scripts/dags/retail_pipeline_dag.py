"""
Cloud Composer (Airflow) DAG: Daily Retail Analytics Pipeline.
Used in Tutorial 4.2: Orchestration with Cloud Composer.

Upload to the Composer DAGs bucket:
  gsutil cp retail_pipeline_dag.py gs://DAGS_BUCKET/retail_pipeline_dag.py

The DAG runs daily at 06:00 UTC and:
  1. Waits for a daily sales CSV to appear in GCS
  2. Loads it into BigQuery (Bronze layer)
  3. Runs SQL transformation to the Silver layer
  4. Refreshes the Gold materialized view summary
  5. Retrains the BigQuery ML model
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.sensors.gcs import GCSObjectExistenceSensor

# ---------------------------------------------------------------------------
# Configuration — update PROJECT_ID and BUCKET for your environment
# ---------------------------------------------------------------------------
PROJECT_ID = "YOUR_PROJECT_ID"   # replace with your GCP project ID
DATASET    = "retail_analytics"
BUCKET     = f"retail-data-{PROJECT_ID}"

# ---------------------------------------------------------------------------
# Default task arguments
# ---------------------------------------------------------------------------
default_args = {
    "owner":            "data-team",
    "depends_on_past":  False,
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
    "email_on_failure": False,
    "email_on_retry":   False,
}

# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id          = "retail_daily_pipeline",
    default_args    = default_args,
    description     = "Daily retail sales ETL: GCS → BigQuery → ML retraining",
    schedule_interval = "0 6 * * *",    # daily at 06:00 UTC
    start_date      = datetime(2024, 1, 1),
    catchup         = False,
    max_active_runs = 1,
    tags            = ["retail", "daily", "bigquery"],
) as dag:

    # ------------------------------------------------------------------
    # Task 1: Wait for today's sales file to land in GCS
    # The file is expected at gs://BUCKET/raw/daily_sales_YYYY-MM-DD.csv
    # ------------------------------------------------------------------
    check_new_file = GCSObjectExistenceSensor(
        task_id      = "check_new_files",
        bucket       = BUCKET,
        object       = "raw/daily_sales_{{ ds }}.csv",
        timeout      = 3600,          # wait up to 1 hour
        poke_interval = 60,           # check every 60 seconds
        mode         = "reschedule",  # release worker slot while waiting
    )

    # ------------------------------------------------------------------
    # Task 2: Load raw CSV into BigQuery (Bronze table)
    # ------------------------------------------------------------------
    load_raw = BigQueryInsertJobOperator(
        task_id = "load_raw_to_bigquery",
        configuration = {
            "load": {
                "sourceUris": [f"gs://{BUCKET}/raw/daily_sales_{{{{ ds }}}}.csv"],
                "destinationTable": {
                    "projectId": PROJECT_ID,
                    "datasetId": DATASET,
                    "tableId":   "raw_sales",
                },
                "sourceFormat":     "CSV",
                "writeDisposition": "WRITE_APPEND",
                "skipLeadingRows":  1,
                "autodetect":       True,
            }
        },
    )

    # ------------------------------------------------------------------
    # Task 3: Silver layer transformation — insert cleaned rows
    # ------------------------------------------------------------------
    run_silver = BigQueryInsertJobOperator(
        task_id = "run_silver_transformation",
        configuration = {
            "query": {
                "query": f"""
                    -- Re-create the Silver view to pick up schema changes
                    CREATE OR REPLACE VIEW `{PROJECT_ID}.{DATASET}.clean_sales` AS
                    SELECT
                        PARSE_DATE('%Y-%m-%d', date)  AS sale_date,
                        TRIM(LOWER(store_id))         AS store_id,
                        TRIM(LOWER(product))          AS product,
                        TRIM(LOWER(category))         AS category,
                        CAST(quantity  AS INT64)      AS quantity,
                        CAST(unit_price AS FLOAT64)   AS unit_price,
                        CAST(revenue   AS FLOAT64)    AS revenue
                    FROM `{PROJECT_ID}.{DATASET}.raw_sales`
                    WHERE quantity IS NOT NULL
                      AND SAFE_CAST(revenue AS FLOAT64) > 0
                """,
                "useLegacySql": False,
            }
        },
    )

    # ------------------------------------------------------------------
    # Task 4: Refresh Gold layer — rebuild daily aggregation table
    # (Materialized Views refresh automatically, but for a scheduled
    #  full refresh we can also explicitly recreate the summary table)
    # ------------------------------------------------------------------
    refresh_gold = BigQueryInsertJobOperator(
        task_id = "refresh_gold_summary",
        configuration = {
            "query": {
                "query": f"""
                    CREATE OR REPLACE TABLE `{PROJECT_ID}.{DATASET}.monthly_kpi_report`
                    PARTITION BY month
                    AS
                    SELECT
                        DATE_TRUNC(sale_date, MONTH)  AS month,
                        store_id,
                        category,
                        SUM(revenue)                  AS monthly_revenue,
                        SUM(quantity)                 AS monthly_units,
                        COUNT(*)                      AS transactions
                    FROM `{PROJECT_ID}.{DATASET}.clean_sales`
                    GROUP BY month, store_id, category
                    ORDER BY month DESC, monthly_revenue DESC
                """,
                "useLegacySql": False,
            }
        },
    )

    # ------------------------------------------------------------------
    # Task 5: Retrain the BigQuery ML model on fresh data
    # ------------------------------------------------------------------
    retrain_model = BigQueryInsertJobOperator(
        task_id = "retrain_bqml_model",
        configuration = {
            "query": {
                "query": f"""
                    CREATE OR REPLACE MODEL `{PROJECT_ID}.{DATASET}.trip_duration_model`
                    OPTIONS (
                        model_type        = 'linear_reg',
                        input_label_cols  = ['label'],
                        data_split_method = 'auto_split'
                    ) AS
                    SELECT
                        CAST(trip_miles AS FLOAT64)                      AS trip_miles,
                        IFNULL(CAST(pickup_community_area  AS INT64), 0) AS pickup_area,
                        IFNULL(CAST(dropoff_community_area AS INT64), 0) AS dropoff_area,
                        CAST(fare AS FLOAT64)                            AS fare,
                        CASE payment_type WHEN 'Credit Card' THEN 1
                                          WHEN 'Cash'        THEN 2
                                          ELSE 0 END                     AS payment_type_encoded,
                        CAST(trip_seconds AS INT64)                      AS label
                    FROM `bigquery-public-data.chicago_taxi_trips.taxi_trips`
                    WHERE trip_start_timestamp > TIMESTAMP_SUB(
                              CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
                      AND trip_seconds BETWEEN 60 AND 7200
                      AND trip_miles   BETWEEN 0.1 AND 50
                      AND fare         BETWEEN 2.5 AND 200
                """,
                "useLegacySql": False,
            }
        },
    )

    # ------------------------------------------------------------------
    # Execution order
    # ------------------------------------------------------------------
    check_new_file >> load_raw >> run_silver >> refresh_gold >> retrain_model
