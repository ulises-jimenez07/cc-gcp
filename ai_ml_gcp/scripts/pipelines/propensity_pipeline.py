"""
Vertex AI Pipeline — Customer Propensity Model.
Used in Tutorial 3.1: Vertex AI Pipelines (KubeFlow).

Pipeline steps:
  1. preprocess_data  — validate and export training data from BigQuery to GCS
  2. train_model      — train GradientBoostingClassifier in a custom container
  3. evaluate_model   — compute AUC on test split
  4. upload_model     — conditionally register in Vertex AI Model Registry

Usage:
  python3 propensity_pipeline.py --project=YOUR_PROJECT --bucket=ml-artifacts-PROJECT
"""

import argparse

from kfp.v2 import dsl, compiler
from kfp.v2.dsl import (
    component,
    Condition,
    Input,
    Output,
    Dataset,
    Model,
    Metrics,
    ClassificationMetrics,
)


# ── Component 1: Preprocess ────────────────────────────────────────────────

@component(
    base_image="python:3.10-slim",
    packages_to_install=[
        "google-cloud-bigquery==3.23.1",
        "db-dtypes==1.3.0",
        "pandas==2.2.2",
    ],
)
def preprocess_data(
    project: str,
    sample_size: int,
    train_data: Output[Dataset],
    test_data: Output[Dataset],
):
    """Export BigQuery census data to GCS as CSV for training."""
    import pandas as pd
    from google.cloud import bigquery
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import LabelEncoder

    client = bigquery.Client(project=project)
    df = client.query(f"""
        SELECT age, workclass, education, marital_status,
               occupation, hours_per_week, income_bracket
        FROM `bigquery-public-data.ml_datasets.census_adult_income`
        WHERE age BETWEEN 18 AND 70
        LIMIT {sample_size}
    """).to_dataframe()

    for col in df.select_dtypes("object").columns:
        df[col] = LabelEncoder().fit_transform(df[col].astype(str))

    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)
    train_df.to_csv(train_data.path, index=False)
    test_df.to_csv(test_data.path, index=False)

    print(f"Train: {len(train_df)} rows, Test: {len(test_df)} rows")


# ── Component 2: Train ─────────────────────────────────────────────────────

@component(
    base_image="python:3.10-slim",
    packages_to_install=[
        "scikit-learn==1.4.2",
        "pandas==2.2.2",
        "joblib==1.4.2",
    ],
)
def train_model(
    train_data: Input[Dataset],
    model_artifact: Output[Model],
    learning_rate: float,
    max_depth: int,
    n_estimators: int,
):
    """Train a GradientBoostingClassifier."""
    import joblib, os
    import pandas as pd
    from sklearn.ensemble import GradientBoostingClassifier

    df = pd.read_csv(train_data.path)
    X = df.drop("income_bracket", axis=1)
    y = df["income_bracket"]

    clf = GradientBoostingClassifier(
        learning_rate=learning_rate,
        max_depth=max_depth,
        n_estimators=n_estimators,
        random_state=42,
    )
    clf.fit(X, y)

    os.makedirs(model_artifact.path, exist_ok=True)
    joblib.dump(clf, os.path.join(model_artifact.path, "model.joblib"))
    print("Model trained and saved.")


# ── Component 3: Evaluate ──────────────────────────────────────────────────

@component(
    base_image="python:3.10-slim",
    packages_to_install=[
        "scikit-learn==1.4.2",
        "pandas==2.2.2",
        "joblib==1.4.2",
    ],
)
def evaluate_model(
    test_data: Input[Dataset],
    model_artifact: Input[Model],
    metrics: Output[Metrics],
    classification_metrics: Output[ClassificationMetrics],
) -> float:
    """Evaluate the model and return AUC."""
    import joblib, os
    import pandas as pd
    from sklearn.metrics import roc_auc_score, confusion_matrix

    df = pd.read_csv(test_data.path)
    X = df.drop("income_bracket", axis=1)
    y = df["income_bracket"]

    clf = joblib.load(os.path.join(model_artifact.path, "model.joblib"))
    y_pred = clf.predict(X)
    y_proba = clf.predict_proba(X)[:, 1]

    auc = roc_auc_score(y, y_proba)
    metrics.log_metric("auc", auc)
    metrics.log_metric("framework", "sklearn")

    cm = confusion_matrix(y, y_pred)
    classification_metrics.log_confusion_matrix(
        ["<=50K", ">50K"],
        cm.tolist()
    )

    print(f"AUC: {auc:.4f}")
    return auc


# ── Component 4: Upload ────────────────────────────────────────────────────

@component(
    base_image="python:3.10-slim",
    packages_to_install=["google-cloud-aiplatform==1.57.0"],
)
def upload_model(
    project: str,
    region: str,
    model_artifact: Input[Model],
    model_display_name: str,
):
    """Register the model in Vertex AI Model Registry."""
    import google.cloud.aiplatform as aip

    aip.init(project=project, location=region)

    model = aip.Model.upload(
        display_name=model_display_name,
        artifact_uri=model_artifact.uri,
        serving_container_image_uri=(
            "us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-3:latest"
        ),
    )
    print(f"Model registered: {model.resource_name}")


# ── Pipeline definition ────────────────────────────────────────────────────

@dsl.pipeline(
    name="propensity-model-pipeline",
    description="Preprocess, train, evaluate, and conditionally register the propensity model.",
)
def propensity_pipeline(
    project: str,
    region: str = "us-central1",
    sample_size: int = 10000,
    learning_rate: float = 0.08,
    max_depth: int = 5,
    n_estimators: int = 200,
    auc_threshold: float = 0.80,
    model_display_name: str = "propensity-model",
):
    preprocess_task = preprocess_data(
        project=project,
        sample_size=sample_size,
    )

    train_task = train_model(
        train_data=preprocess_task.outputs["train_data"],
        learning_rate=learning_rate,
        max_depth=max_depth,
        n_estimators=n_estimators,
    )

    evaluate_task = evaluate_model(
        test_data=preprocess_task.outputs["test_data"],
        model_artifact=train_task.outputs["model_artifact"],
    )

    with Condition(evaluate_task.output >= auc_threshold, name="auc-check"):
        upload_model(
            project=project,
            region=region,
            model_artifact=train_task.outputs["model_artifact"],
            model_display_name=model_display_name,
        )


# ── CLI entrypoint ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project",  required=True)
    parser.add_argument("--bucket",   required=True)
    parser.add_argument("--image",    default="")
    parser.add_argument("--region",   default="us-central1")
    parser.add_argument("--wait",     action="store_true")
    args = parser.parse_args()

    import google.cloud.aiplatform as aip

    # Compile
    compiler.Compiler().compile(
        pipeline_func=propensity_pipeline,
        package_path="propensity_pipeline.json",
    )
    print("Pipeline compiled to propensity_pipeline.json")

    # Submit
    aip.init(project=args.project, location=args.region,
             staging_bucket=f"gs://{args.bucket}")

    job = aip.PipelineJob(
        display_name="propensity-pipeline-run",
        template_path="propensity_pipeline.json",
        pipeline_root=f"gs://{args.bucket}/pipeline_root",
        parameter_values={
            "project": args.project,
            "region": args.region,
        },
    )

    job.run(sync=args.wait)
    print(f"Pipeline job submitted: {job.resource_name}")
