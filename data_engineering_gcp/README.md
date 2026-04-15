# Global Retail Analytics Platform on GCP

A hands-on tutorial series that builds a **Global Retail Analytics Platform**, evolving from traditional Hadoop/Spark batch processing to a modern, serverless, real-time data architecture on Google Cloud Platform.

---

## The Pipeline

We evolve one analytics platform across four architectural eras:

| Phase | Architecture | GCP Services |
|-------|-------------|-------------|
| 1 | The Hadoop Era | Dataproc (MapReduce, Spark) |
| 2 | Modern Data Warehousing | BigQuery, Public Datasets |
| 3 | Serverless Analytics & ML | BigQuery ML, Materialized Views, Scheduled Queries |
| 4 | Real-Time & Orchestration | Dataflow (Streaming), Cloud Composer (Airflow) |

---

## Tutorials

### Phase 1 — The Hadoop Era (Managed Clusters)

| Tutorial | Topic |
|----------|-------|
| [1.1 Dataproc & MapReduce](./phase1_hadoop_era/01_dataproc_mapreduce.md) | Process raw logs with Hadoop on a managed Dataproc cluster |
| [1.2 Moving to Spark](./phase1_hadoop_era/02_spark.md) | Replace MapReduce with in-memory Spark jobs for faster processing |

### Phase 2 — Serverless Warehousing & Public Data

| Tutorial | Topic |
|----------|-------|
| [2.1 BigQuery Ingestion & Public Datasets](./phase2_warehousing/01_bigquery_ingestion.md) | Query millions of rows without managing infrastructure |
| [2.2 Partitioning & Clustering](./phase2_warehousing/02_optimization.md) | Reduce query costs and latency with physical data layout |

### Phase 3 — Serverless Analytics & ML

| Tutorial | Topic |
|----------|-------|
| [3.1 Views, Materialized Views & Scheduled Queries](./phase3_analytics_ml/01_views_scheduled_queries.md) | Build a Bronze/Silver/Gold data warehouse using only SQL |
| [3.2 BigQuery ML](./phase3_analytics_ml/02_bigquery_ml.md) | Train and serve ML models with SQL — no separate infrastructure |

### Phase 4 — Real-Time & Orchestration

| Tutorial | Topic |
|----------|-------|
| [4.1 Streaming with Pub/Sub & Dataflow](./phase4_realtime_orchestration/01_streaming_dataflow.md) | Ingest live events and write to BigQuery with zero latency |
| [4.2 Orchestration with Cloud Composer](./phase4_realtime_orchestration/02_composer_airflow.md) | Automate multi-step pipelines with managed Apache Airflow |

---

## Scripts & Code

Reusable scripts live in [scripts/](./scripts/):

```
scripts/
├── pyspark/
│   ├── word_count.py          — MapReduce-style word count (Dataproc)
│   └── clean_and_transform.py — Spark ETL: GCS → Parquet
├── sql/
│   ├── create_optimized_table.sql   — partitioned + clustered BigQuery table
│   ├── bronze_silver_gold.sql       — layered views
│   └── bqml_model.sql               — BigQuery ML model creation + prediction
└── dags/
    └── retail_pipeline_dag.py       — Cloud Composer (Airflow) DAG
```

---

## Prerequisites

- A GCP project with billing enabled (see [root README](../README.md#prerequisites) for setup)
- `gcloud` CLI installed and authenticated
- Basic familiarity with SQL and Python
