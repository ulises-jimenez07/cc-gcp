# Tutorial 4.2: Orchestration with Cloud Composer (Airflow)

You now have four pipeline components — Dataproc batch jobs, BigQuery loads, SQL transformations, and ML retraining. Running them manually in the right order, handling failures, and retrying is unsustainable. **Apache Airflow** is the industry standard for orchestrating data pipelines.

**Cloud Composer** is fully managed Airflow on GCP. You write Python **DAGs** (Directed Acyclic Graphs) and upload them to a GCS bucket. Composer schedules and monitors execution automatically.

```mermaid
graph TD
    Start([Start]) --> S1[check_new_files_in_gcs<br/>GCSSensor]
    S1 --> S2[load_raw_to_bigquery<br/>BigQueryInsertJobOperator]
    S2 --> S3[run_silver_transformation<br/>BigQueryInsertJobOperator]
    S3 --> S4[refresh_materialized_views<br/>BigQueryInsertJobOperator]
    S4 --> S5[retrain_bqml_model<br/>BigQueryInsertJobOperator]
    S5 --> S6[notify_on_success<br/>optional HTTP/email operator]
```

**Previous tutorial:** [4.1 Streaming with Dataflow](./01_streaming_dataflow.md)

---

## 1. Enable APIs

```bash
gcloud services enable \
  composer.googleapis.com \
  storage.googleapis.com
```

---

## 2. Create a Cloud Composer Environment

**This takes 20–30 minutes.** It provisions a GKE cluster running Airflow, a GCS bucket for DAGs, and a Cloud SQL instance for the Airflow metadata database.

### Console

1. **Composer > Create Environment**
2. **Environment name**: `retail-pipeline-env`
3. **Location**: `us-central1`
4. **Image version**: `composer-2-airflow-2` (latest)
5. **Node count**: 3 (minimum)
6. Click **Create**

### gcloud CLI

```bash
gcloud composer environments create retail-pipeline-env \
  --location=us-central1 \
  --image-version=composer-2-airflow-2
```

Monitor creation:

```bash
gcloud composer environments describe retail-pipeline-env \
  --location=us-central1 \
  --format='get(state)'
```

---

## 3. Get the DAGs bucket

Every file in the environment's GCS `dags/` folder is automatically picked up by Airflow:

```bash
# Get the GCS bucket name for this Composer environment
DAGS_BUCKET=$(gcloud composer environments describe retail-pipeline-env \
  --location=us-central1 \
  --format='get(config.dagGcsPrefix)')

echo "DAGs bucket: $DAGS_BUCKET"
```

---

## 4. Review the DAG

The DAG is at [scripts/dags/retail_pipeline_dag.py](../scripts/dags/retail_pipeline_dag.py).

Key structure:

```python
from airflow import DAG
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.sensors.gcs import GCSObjectExistenceSensor
from datetime import datetime, timedelta

PROJECT_ID = "YOUR_PROJECT_ID"
DATASET = "retail_analytics"
BUCKET = f"retail-data-{PROJECT_ID}"

default_args = {
    'owner': 'data-team',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email_on_failure': False,
}

with DAG(
    dag_id='retail_daily_pipeline',
    default_args=default_args,
    schedule_interval='0 6 * * *',   # daily at 06:00 UTC
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['retail', 'daily'],
) as dag:

    # Step 1: wait for new data to arrive in GCS
    check_new_file = GCSObjectExistenceSensor(
        task_id='check_new_files',
        bucket=BUCKET,
        object='raw/daily_sales_{{ ds }}.csv',
        timeout=3600,
        poke_interval=60,
    )

    # Step 2: load raw CSV into BigQuery
    load_raw = BigQueryInsertJobOperator(
        task_id='load_raw_to_bigquery',
        configuration={
            'load': {
                'sourceUris': [f'gs://{BUCKET}/raw/daily_sales_{{{{ ds }}}}.csv'],
                'destinationTable': {
                    'projectId': PROJECT_ID,
                    'datasetId': DATASET,
                    'tableId': 'raw_sales',
                },
                'sourceFormat': 'CSV',
                'writeDisposition': 'WRITE_APPEND',
                'skipLeadingRows': 1,
                'autodetect': True,
            }
        },
    )

    # Step 3: run SQL transformation (Silver layer)
    run_silver = BigQueryInsertJobOperator(
        task_id='run_silver_transformation',
        configuration={
            'query': {
                'query': """
                    INSERT INTO `{{ params.project }}.retail_analytics.clean_sales`
                    SELECT
                        PARSE_DATE('%Y-%m-%d', date) AS sale_date,
                        TRIM(LOWER(store_id)) AS store_id,
                        TRIM(LOWER(product)) AS product,
                        TRIM(LOWER(category)) AS category,
                        CAST(quantity AS INT64) AS quantity,
                        CAST(unit_price AS FLOAT64) AS unit_price,
                        CAST(revenue AS FLOAT64) AS revenue
                    FROM `{{ params.project }}.retail_analytics.raw_sales`
                    WHERE DATE(PARSE_DATE('%Y-%m-%d', date)) = '{{ ds }}'
                      AND quantity IS NOT NULL AND revenue > 0
                """,
                'useLegacySql': False,
            }
        },
        params={'project': PROJECT_ID},
    )

    # Step 4: retrain the ML model
    retrain_model = BigQueryInsertJobOperator(
        task_id='retrain_bqml_model',
        configuration={
            'query': {
                'query': f"""
                    CREATE OR REPLACE MODEL `{PROJECT_ID}.{DATASET}.trip_duration_model`
                    OPTIONS (model_type = 'linear_reg', input_label_cols = ['label'])
                    AS
                    SELECT trip_miles, pickup_area, dropoff_area, fare,
                           payment_type_encoded, trip_seconds AS label
                    FROM `{PROJECT_ID}.{DATASET}.taxi_training_data`
                """,
                'useLegacySql': False,
            }
        },
    )

    # Define execution order
    check_new_file >> load_raw >> run_silver >> retrain_model
```

---

## 5. Upload the DAG to Composer

```bash
PROJECT_ID=$(gcloud config get-value project)

# Replace placeholder in the DAG
sed "s/YOUR_PROJECT_ID/$PROJECT_ID/g" \
  scripts/dags/retail_pipeline_dag.py > /tmp/retail_pipeline_dag.py

# Upload to the DAGs bucket
gsutil cp /tmp/retail_pipeline_dag.py $DAGS_BUCKET/retail_pipeline_dag.py
```

Airflow picks up the file within ~30 seconds. No restart required.

---

## 6. Open the Airflow UI

```bash
# Get the Airflow web UI URL
gcloud composer environments describe retail-pipeline-env \
  --location=us-central1 \
  --format='get(config.airflowUri)'
```

1. Navigate to the URL in your browser
2. **DAGs > retail_daily_pipeline** — you should see the DAG graph
3. Toggle the DAG **On** (it's paused by default)

---

## 7. Trigger a manual run

```bash
# Trigger the DAG from the CLI
gcloud composer environments run retail-pipeline-env \
  --location=us-central1 \
  dags trigger \
  -- retail_daily_pipeline
```

Or click **Trigger DAG** in the Airflow UI.

---

## 8. Monitor execution

### Console (Airflow UI)

- **DAGs > retail_daily_pipeline > Graph View** — real-time status of each task (green = success, red = failed, yellow = running)
- **DAGs > retail_daily_pipeline > Grid View** — historical runs at a glance

### gcloud CLI

```bash
# List recent DAG runs
gcloud composer environments run retail-pipeline-env \
  --location=us-central1 \
  dags list-runs \
  -- -d retail_daily_pipeline

# View task logs
gcloud composer environments run retail-pipeline-env \
  --location=us-central1 \
  tasks log \
  -- retail_daily_pipeline load_raw_to_bigquery $(date +%Y-%m-%dT%H:%M:%S)
```

---

## 9. Add an SLA and alerting

```python
# Add to the DAG definition:
from airflow.models import SlaMiss

def sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis):
    print(f"SLA missed for tasks: {task_list}")
    # Send to Slack, PagerDuty, etc.

with DAG(
    dag_id='retail_daily_pipeline',
    sla_miss_callback=sla_miss_callback,
    ...
) as dag:
    load_raw = BigQueryInsertJobOperator(
        ...,
        sla=timedelta(hours=2),   # alert if task takes > 2 hours
    )
```

---

## 10. Delete the Composer environment (cost control)

Composer environments cost ~$300+/month even when idle. Delete when done with the tutorial:

```bash
gcloud composer environments delete retail-pipeline-env \
  --location=us-central1 \
  --quiet
```

---

## 11. Complete pipeline architecture

```mermaid
graph TD
    DS[Data Sources<br/>POS, APIs, files] --> PS[Pub/Sub<br/>retail-events]
    
    PS --> StreamingPath
    PS --> BatchPath

    subgraph StreamingPath [Streaming Path]
        DF[Dataflow] --> BQS[BigQuery<br/>live_sales_events]
    end
    
    subgraph BatchPath [Batch Path: Cloud Composer DAG, daily]
        GCS[GCS<br/>raw CSV files] --> BQL[BigQuery Load]
        BQL --> BR[raw_sales<br/>Bronze]
        BR --> SQL[SQL Transform]
        SQL --> SV[clean_sales view<br/>Silver]
        SV --> MV[Materialized View]
        MV --> DR[daily_revenue_by_store<br/>Gold]
        DR --> BML[BigQuery ML]
        BML --> RF[revenue_forecast model]
        RF --> SQ[Scheduled Query]
        SQ --> MK[monthly_kpi_report<br/>BI layer]
    end
```

---

## Congratulations

You have completed the full data engineering roadmap:

| Phase | What you built |
|-------|---------------|
| 1.1 | Dataproc cluster + Hadoop MapReduce job |
| 1.2 | PySpark ETL writing Parquet to GCS |
| 2.1 | BigQuery dataset + Public Dataset queries |
| 2.2 | Partitioned + clustered tables (90%+ cost reduction) |
| 3.1 | Bronze/Silver/Gold with Views, Materialized Views, Scheduled Queries |
| 3.2 | BigQuery ML: linear regression + ARIMA time-series forecast |
| 4.1 | Streaming pipeline: Pub/Sub → Dataflow → BigQuery |
| 4.2 | Cloud Composer DAG orchestrating the full batch pipeline |

The platform evolved from a cluster-based batch job requiring hours to spin up, to a fully serverless, real-time analytics platform capable of processing millions of events per second and training ML models at the scale of the data itself.
