"""
PySpark ETL job: Analyze Chicago Taxi Trips public data.
Used in Tutorial 1.2: Moving to Spark.

Submit to Dataproc:
  gcloud dataproc jobs submit pyspark gs://BUCKET/scripts/clean_and_transform.py \
    --cluster=spark-cluster \
    --region=us-central1 \
    -- --output=gs://BUCKET/processed/taxi_summary/
"""

import argparse
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def main(output_path: str):
    spark = SparkSession.builder \
        .appName("ChicagoTaxiETL") \
        .getOrCreate()

    # Suppress verbose logging
    spark.sparkContext.setLogLevel("WARN")

    print("Reading data from bigquery-public-data.chicago_taxi_trips.taxi_trips")
    
    # Read from BigQuery Public Dataset
    df = spark.read.format("bigquery") \
        .option("table", "bigquery-public-data.chicago_taxi_trips.taxi_trips") \
        .load()

    # Filter for long trips and standardize payment type
    df_filtered = df \
        .filter(F.col("trip_miles") > 5) \
        .filter(F.col("fare") > 0) \
        .withColumn("payment_type", F.lower(F.col("payment_type")))

    # Aggregate: avg fare and total tips by payment type
    summary = df_filtered.groupBy("payment_type").agg(
        F.round(F.avg("fare"), 2).alias("avg_fare"),
        F.round(F.sum("tips"), 2).alias("total_tips"),
        F.count("*").alias("trip_count")
    ).orderBy(F.col("total_tips").desc())

    print(f"Writing Parquet to: {output_path}")

    # Write as Parquet
    summary.write \
        .mode("overwrite") \
        .parquet(output_path)

    print("ETL job complete.")

    # Show a sample of the output
    summary.show(20)

    spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chicago Taxi ETL with PySpark")
    parser.add_argument("--output", required=True, help="GCS path for Parquet output")
    args = parser.parse_args()

    main(args.output)
