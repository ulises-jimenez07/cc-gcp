# GCP Hands-On Tutorial Series

A collection of hands-on tutorial series for building real-world systems on Google Cloud Platform, organized by domain.

**Author:** Ulises Jimenez
**Last updated:** 2026-03-27

---

## Roadmaps

| Directory | Topic |
|-----------|-------|
| [web_app_gcp/](./web_app_gcp/) | Scaling a Node.js app from a single VM to a fully containerized, globally distributed system |
| [data_engineering_gcp/](./data_engineering_gcp/) | Evolving a data pipeline from Hadoop/Spark clusters to serverless BigQuery, ML, and real-time streaming |
| [ai_ml_gcp/](./ai_ml_gcp/) | Building intelligent applications with Vertex AI, Gemini, and agent architectures on GCP |

---

## Prerequisites

Before starting any tutorial, ensure you have a GCP project and your environment configured.

### 1. Create a GCP Project
1. Go to the [GCP Console](https://console.cloud.google.com/).
2. Click on the project dropdown list at the top of the page.
3. Click **New Project**.
4. Enter a Project Name (e.g., `GCP Hands-On Tutorials`).
5. (Optional) Edit the Project ID.
6. Click **Create**.

### 2. Authenticate and Set Up CLI
1. Run the following commands to authenticate your account and set up Application Default Credentials:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```
2. Set the default project for your current work:
   ```bash
   gcloud config set project <PROJECT_ID>
   ```

### 3. Other Requirements
- A GCP project with billing enabled.
- Basic familiarity with the language/framework used in each roadmap.
