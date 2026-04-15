"""
Vertex AI Custom Training Job — Propensity Model.
Used in Tutorial 2.1: Distributed Training with Custom Containers.

The script:
  1. Fetches training data from BigQuery (US Census income dataset)
  2. Trains a GradientBoostingClassifier
  3. Evaluates on a hold-out test set (reports AUC)
  4. Saves the model artifact to AIP_MODEL_DIR (injected by Vertex AI)
  5. Reports the AUC metric to hypertune (used by HP Tuning in Tutorial 2.2)

Environment variables set automatically by Vertex AI:
  AIP_MODEL_DIR  — GCS URI where artifacts should be written
  AIP_DATA_FORMAT, AIP_TRAINING_DATA_URI — if using managed datasets
"""

import argparse
import json
import logging
import os
import sys

import joblib
import pandas as pd
from google.cloud import bigquery
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project",       type=str, default=os.environ.get("CLOUD_ML_PROJECT_ID", ""))
    parser.add_argument("--model-dir",     type=str, default=os.environ.get("AIP_MODEL_DIR", "/tmp/model"))
    parser.add_argument("--learning-rate", type=float, default=0.08)
    parser.add_argument("--max-depth",     type=int,   default=5)
    parser.add_argument("--n-estimators",  type=int,   default=200)
    parser.add_argument("--sample-size",   type=int,   default=10000,
                        help="Row limit for BigQuery query (use smaller value for PR checks)")
    return parser.parse_args()


def fetch_data(project: str, sample_size: int) -> pd.DataFrame:
    log.info("Fetching data from BigQuery...")
    client = bigquery.Client(project=project)
    query = f"""
        SELECT
            age, workclass, education, marital_status,
            occupation, hours_per_week, income_bracket
        FROM `bigquery-public-data.ml_datasets.census_adult_income`
        WHERE age BETWEEN 18 AND 70
        LIMIT {sample_size}
    """
    df = client.query(query).to_dataframe()
    log.info(f"Fetched {len(df)} rows")
    return df


def preprocess(df: pd.DataFrame):
    df = df.copy()
    for col in df.select_dtypes("object").columns:
        df[col] = LabelEncoder().fit_transform(df[col].astype(str))
    X = df.drop("income_bracket", axis=1)
    y = df["income_bracket"]
    return train_test_split(X, y, test_size=0.2, random_state=42)


def train(X_train, y_train, learning_rate: float, max_depth: int, n_estimators: int):
    log.info(f"Training: lr={learning_rate}, depth={max_depth}, n={n_estimators}")
    clf = GradientBoostingClassifier(
        learning_rate=learning_rate,
        max_depth=max_depth,
        n_estimators=n_estimators,
        random_state=42,
    )
    clf.fit(X_train, y_train)
    return clf


def evaluate(clf, X_test, y_test) -> float:
    y_proba = clf.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_proba)
    log.info(f"AUC: {auc:.4f}")
    log.info(classification_report(y_test, clf.predict(X_test)))
    return auc


def save_model(clf, model_dir: str, metadata: dict):
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "propensity_model.joblib")
    joblib.dump(clf, model_path)
    log.info(f"Model saved to {model_path}")

    meta_path = os.path.join(model_dir, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    log.info(f"Metadata saved to {meta_path}")


def report_metric(auc: float):
    """Report AUC to Vertex AI HP Tuning service (Tutorial 2.2)."""
    try:
        import hypertune
        hpt = hypertune.HyperTune()
        hpt.report_hyperparameter_tuning_metric(
            hyperparameter_metric_tag="auc",
            metric_value=auc,
            global_step=1,
        )
        log.info(f"Reported AUC={auc:.4f} to hypertune")
    except ImportError:
        log.info("hypertune not installed — skipping metric report (normal for non-tuning jobs)")


def main():
    args = parse_args()

    df = fetch_data(args.project, args.sample_size)
    X_train, X_test, y_train, y_test = preprocess(df)

    clf = train(X_train, y_train, args.learning_rate, args.max_depth, args.n_estimators)
    auc = evaluate(clf, X_test, y_test)

    metadata = {
        "framework": "sklearn",
        "model_type": "GradientBoostingClassifier",
        "hyperparameters": {
            "learning_rate": args.learning_rate,
            "max_depth": args.max_depth,
            "n_estimators": args.n_estimators,
        },
        "metrics": {"auc": auc},
        "train_rows": len(X_train),
        "test_rows": len(X_test),
    }

    save_model(clf, args.model_dir, metadata)
    report_metric(auc)

    log.info("Training complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()
