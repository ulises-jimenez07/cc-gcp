# Scaling from Zero to Millions on GCP (Python Edition)

A hands-on tutorial series that builds an **Image Processing & Storage App** in Python, evolving it from a single VM all the way to a fully containerized, auto-scaling system on Google Cloud Platform.

Follows the evolutionary scaling path described in *System Design Interview* (Alex Xu), Chapter 1.

---

## The App

We build one application across five versions:

| Version | What changes |
|---------|-------------|
| v1 | FastAPI app on a single VM, images stored locally, MariaDB on the same machine |
| v2 | App connects to **Cloud SQL** (MySQL) via Private IP |
| v3 | Images stored in **GCS**, metadata cached in **Memorystore (Redis)** |
| v4 | App publishes to **Pub/Sub**, background **Cloud Run Function** generates thumbnails |
| v5 | App is containerized, deployed to **Cloud Run / GKE** with **CI/CD** via Cloud Build |

---

## Tutorials

### Phase 1 — The Monolith & Horizontal Growth

| Tutorial | Topic |
|----------|-------|
| [1.1 Single Server Setup](./phase1_monolith/01_single_server_setup.md) | Deploy app + DB on one Compute Engine VM |
| [1.2 Decoupling the Database](./phase1_monolith/02_decoupling_database.md) | Migrate to Cloud SQL with Private IP |
| [1.3 Horizontal Scaling](./phase1_monolith/03_horizontal_scaling.md) | MIGs, autoscaling, and HTTP Load Balancing |

### Phase 2 — Performance & Global Scale

| Tutorial | Topic |
|----------|-------|
| [2.1 Caching with Memorystore](./phase2_performance/01_caching_memorystore.md) | Cache-Aside pattern with Redis |
| [2.2 CDN with Cloud Storage](./phase2_performance/02_cdn.md) | Serve images from global edge locations |

### Phase 3 — Event-Driven Architecture

| Tutorial | Topic |
|----------|-------|
| [3.1 Async Workers (Pub/Sub & Functions)](./phase3_event_driven/01_async_workers_pubsub.md) | Offload thumbnail generation to background workers |

### Phase 4 — Modern Infrastructure (Containers & Kubernetes)

| Tutorial | Topic |
|----------|-------|
| [4.1 Containerization & Cloud Run](./phase4_containers/01_containerization_cloud_run.md) | Dockerfile, Artifact Registry, serverless containers |
| [4.2 Kubernetes Engine (GKE)](./phase4_containers/02_kubernetes_gke.md) | Full orchestration with deployments and services |
| [4.3 Automated CI/CD](./phase4_containers/03_automated_cicd.md) | Push-to-deploy with Cloud Build |

---

## App Source Code

Each version of the app lives in [app/](./app/):

```
app/
├── v1/   — single server (local disk + local MariaDB)
├── v2/   — Cloud SQL via Private IP
├── v3/   — GCS storage + Memorystore Redis cache
├── v4/   — Pub/Sub publishing + Cloud Run Function worker
└── v5/   — containerized, Dockerfile, K8s manifests, cloudbuild.yaml
```

---

## Prerequisites

- A GCP project with billing enabled
- `gcloud` CLI installed and authenticated (`gcloud auth login`)
- Python 3.11+ (for local development)
- Basic familiarity with FastAPI and SQL

## Enable Required APIs

Enable all GCP APIs used across the series in one command:

```bash
gcloud services enable \
  compute.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  storage.googleapis.com \
  pubsub.googleapis.com \
  cloudfunctions.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  container.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  vpcaccess.googleapis.com
```

Each tutorial also notes which API to enable when first using a new service.
