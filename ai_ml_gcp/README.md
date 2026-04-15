# MLOps & AI on Google Cloud

A hands-on tutorial series that builds a **Customer Propensity & Support System**, evolving from a single local notebook experiment to a production-grade MLOps pipeline and an AI-powered support agent — all on Vertex AI.

---

## The System

We build one end-to-end ML system across five phases:

| Phase | Architecture | GCP Services |
|-------|-------------|-------------|
| 1 | Interactive Experimentation | Vertex AI Workbench, BigQuery |
| 2 | Scalable Training & Tuning | Custom Training Jobs, Artifact Registry, Vizier |
| 3 | MLOps Automation | Vertex AI Pipelines (KFP), Model Registry, Model Monitoring |
| 4 | Serving & CI/CD | Online Endpoints, Batch Prediction, Cloud Build |
| 5 | GenAI & Agents | Gemini API, Agent Builder (RAG), Agent SDK (function calling) |

---

## Tutorials

### Phase 1 — Interactive Experimentation

| Tutorial | Topic |
|----------|-------|
| [1.1 Vertex AI Workbench](./phase1_experimentation/01_vertex_ai_workbench.md) | Set up a managed JupyterLab instance, query BigQuery with magic commands, and train a local sklearn model |

### Phase 2 — Scalable Training & Tuning

| Tutorial | Topic |
|----------|-------|
| [2.1 Custom Training Jobs](./phase2_training/01_custom_training.md) | Package training code into a Docker container and submit to Vertex AI managed infrastructure |
| [2.2 Hyperparameter Tuning (Vizier)](./phase2_training/02_hyperparameter_tuning.md) | Use Bayesian optimization to find optimal hyperparameters with parallel trials |

### Phase 3 — MLOps Pipeline

| Tutorial | Topic |
|----------|-------|
| [3.1 Vertex AI Pipelines (KubeFlow)](./phase3_mlops/01_vertex_pipelines.md) | Build a reproducible preprocess → train → evaluate → deploy pipeline with KFP |
| [3.2 Model Registry & Monitoring](./phase3_mlops/02_model_registry_monitoring.md) | Version models and detect training-serving skew and prediction drift |

### Phase 4 — Serving & CI/CD

| Tutorial | Topic |
|----------|-------|
| [4.1 Online Endpoints & Batch Prediction](./phase4_serving/01_endpoints_batch_prediction.md) | Deploy autoscaling real-time endpoints and run async batch scoring jobs |
| [4.2 CI/CD for ML (GitOps)](./phase4_serving/02_cicd_gitops.md) | Automate training and deployment on every Git push with Cloud Build |

### Phase 5 — GenAI & Intelligent Agents

| Tutorial | Topic |
|----------|-------|
| [5.1 Foundation Models & Model Garden](./phase5_genai_agents/01_foundation_models.md) | Use Gemini for text generation, structured classification, vision, and embeddings |
| [5.2 Agent Builder](./phase5_genai_agents/02_agent_builder.md) | Build a RAG-powered support agent with a knowledge base and order-lookup tool |
| [5.3 Agent SDK](./phase5_genai_agents/03_agent_sdk.md) | Write a custom agentic loop in Python that converts natural language to BigQuery SQL |

---

## Scripts & Code

Companion scripts live in [scripts/](./scripts/):

```
scripts/
├── training/
│   ├── train.py              — Custom training job (sklearn propensity model)
│   ├── Dockerfile            — Training container definition
│   ├── requirements.txt      — Python dependencies
│   └── cloudbuild.yaml       — Cloud Build CI/CD pipeline spec
├── pipelines/
│   └── propensity_pipeline.py — KFP v2 pipeline (preprocess → train → evaluate → upload)
└── agents/
    └── analytics_agent.py    — Vertex AI SDK agent with BigQuery function calling
```

---

## Prerequisites

- A GCP project with billing enabled and Vertex AI API enabled (see [root README](../README.md#prerequisites) for setup)
- `gcloud` CLI installed and authenticated
- Python 3.10+, Docker (for Tutorial 2.1 onwards)
- Basic familiarity with Python and ML concepts
