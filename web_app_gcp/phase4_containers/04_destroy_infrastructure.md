# Tutorial 4.4: Destroy Container Infrastructure

In this final step, we will clean up the infrastructure created during Phase 4 (Containerization). This includes the GKE cluster, Cloud Run services, Artifact Registry, and CI/CD triggers.

> **NOTE**: This guide cleans up all infrastructure created across the entire tutorial — container resources (Phase 4), as well as the databases and storage created in earlier phases.

---

## 1. Set environment variables

Set the necessary variables to identify the resources to delete:

```bash
REGION=us-central1
ZONE=us-central1-a
PROJECT_ID=$(gcloud config get-value project)
```

## 2. GKE Cluster

Deleting the GKE cluster will also remove any associated Load Balancer services and persistent volumes created via Kubernetes.

```bash
echo "Removing GKE cluster..."
gcloud container clusters delete scaling-cluster --zone=$ZONE --quiet
```

## 3. Cloud Run Service

Remove the containerized application service and the VPC connector used for private database access:

```bash
echo "Removing Cloud Run service and VPC connector..."
gcloud run services delete image-app --region=$REGION --quiet
gcloud compute networks vpc-access connectors delete app-connector --region=$REGION --quiet
```

## 4. CI/CD Pipeline

Remove the Cloud Build trigger, connection, and Secure Source Manager resources in this order:

```bash
echo "Removing Cloud Build trigger..."
gcloud builds triggers delete deploy-on-push --region=$REGION --quiet

echo "Removing Cloud Build connection (also removes linked repositories)..."
gcloud builds connections delete cc-gcp-connection --region=$REGION --quiet || true

echo "Removing Secure Source Manager repository..."
gcloud source-manager repositories delete cc-gcp \
  --instance=cc-gcp-instance --region=$REGION --quiet || true

echo "Removing Secure Source Manager instance..."
gcloud source-manager instances delete cc-gcp-instance \
  --region=$REGION --quiet || true
```

## 5. Artifact Registry

Delete the Docker repository to stop incurring storage costs for your container images:

```bash
echo "Removing Artifact Registry repository..."
gcloud artifacts repositories delete python-app-repo --location=$REGION --quiet
```

## 6. Cloud SQL

Delete the Cloud SQL instance created in Phase 1. This will permanently destroy the database and all its data:

```bash
echo "Removing Cloud SQL instance..."
gcloud sql instances delete app-db-instance --quiet
```

## 7. Memorystore Redis

Delete the Redis cache instance created in Phase 2:

```bash
echo "Removing Memorystore Redis instance..."
gcloud redis instances delete metadata-cache --region=$REGION --quiet
```

## 8. Cloud Storage Bucket

Delete the image storage bucket and all its contents created in Phase 2:

```bash
BUCKET_NAME=my-app-images-$PROJECT_ID

echo "Removing all objects from bucket..."
gsutil -m rm -r gs://$BUCKET_NAME || true

echo "Removing Cloud Storage bucket..."
gsutil rb gs://$BUCKET_NAME
```

## 9. Secrets (Optional)

If you no longer need the database password stored in Secret Manager:

```bash
echo "Removing secrets..."
gcloud secrets delete db-password --quiet || true
```

---

## Final Verification

To ensure all resources have been removed, you can check:

```bash
# Should show no running clusters
gcloud container clusters list

# Should show no Cloud Run services
gcloud run services list

# Should show no active images
gcloud artifacts docker images list us-central1-docker.pkg.dev/$PROJECT_ID/python-app-repo

# Should show no SQL instances
gcloud sql instances list

# Should show no Redis instances
gcloud redis instances list --region=$REGION

# Should show no project bucket
gsutil ls
```

## Congratulations!

You have successfully built, scaled, and eventually cleaned up a modern, containerized, event-driven web application on Google Cloud Platform.
