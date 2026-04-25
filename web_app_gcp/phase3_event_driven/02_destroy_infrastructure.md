# Tutorial 3.2: Destroy Infrastructure

In Phase 4 (Containerization), we will move away from Virtual Machines (VMs) and the infrastructure we've built so far to focus exclusively on container-based deployments using Google Kubernetes Engine (GKE) and Cloud Run.

Before proceeding to the next phase, we will completely clean up the environment to stop incurring costs and ensure a clean slate.

> **WARNING**: This permanently deletes the database, the Redis cache, Cloud Storage buckets, the Cloud Run Function, the Load Balancer, and all related networking infrastructure created in Phases 1, 2, and 3.

---

## 1. Set environment variables

Set the necessary variables to identify the resources to delete:

```bash
PROJECT_ID=$(gcloud config get-value project)
REGION=us-central1
ZONE=us-central1-a
DB_INSTANCE=app-db-instance
GCS_BUCKET=my-app-images-$PROJECT_ID
STAGING_BUCKET=${PROJECT_ID}-function-staging
FUNCTION_NAME=thumbnail-worker
PUBSUB_TOPIC=image-upload
```

## 2. Load Balancer

Remove the global HTTP load balancer, its components, and the static IP:

```bash
echo "Removing load balancer..."
gcloud compute forwarding-rules delete app-forwarding-rule --global --quiet
gcloud compute target-http-proxies delete app-http-proxy --quiet
gcloud compute url-maps delete app-url-map --quiet
gcloud compute backend-services delete app-backend --global --quiet
gcloud compute addresses delete app-lb-ip --global --quiet
gcloud compute backend-buckets delete img-backend-bucket --quiet
```

## 3. Managed Instance Group (MIG)

Delete the Managed Instance Group that handled our horizontal scaling:

```bash
echo "Removing MIG..."
gcloud compute instance-groups managed delete app-mig --zone=$ZONE --quiet
```

## 4. Health Check & Instance Templates

Remove the health check and the instance templates we used across app versions (adjust template names if you created different versions):

```bash
echo "Removing health check and instance templates..."
gcloud compute health-checks delete app-health-check --quiet
gcloud compute instance-templates delete app-template-v4 --quiet
gcloud compute instance-templates delete app-template-v3 --quiet
gcloud compute instance-templates delete app-template-v2 --quiet
gcloud compute instance-templates delete app-template-v1 --quiet
```

## 5. Cloud Run Function & Pub/Sub

Delete the event-driven components created in Phase 3:

```bash
echo "Removing Cloud Run Function..."
gcloud functions delete $FUNCTION_NAME --region=$REGION --gen2 --quiet

echo "Removing Pub/Sub topic..."
gcloud pubsub topics delete $PUBSUB_TOPIC --quiet

echo "Removing thumbnail-worker service account..."
gcloud iam service-accounts delete thumbnail-worker-sa@$PROJECT_ID.iam.gserviceaccount.com --quiet
```

## 6. Cloud Storage Buckets

Empty and delete both the staging bucket for the function and the main images bucket:

```bash
echo "Removing function staging bucket..."
gsutil -m rm -r gs://$STAGING_BUCKET/** || true
gcloud storage buckets delete gs://$STAGING_BUCKET --quiet || true

echo "Removing GCS images bucket..."
gsutil -m rm -r gs://$GCS_BUCKET/** || true
gcloud storage buckets delete gs://$GCS_BUCKET --quiet || true
```

## 7. Memorystore (Redis)

Delete the Redis instance used for caching metadata:

```bash
echo "Removing Memorystore Redis..."
gcloud redis instances delete metadata-cache --region=$REGION --quiet
```

## 8. Monolith VM

Delete the original `monolith-server` VM we used to build and configure the application manually:

```bash
echo "Removing monolith-server VM..."
gcloud compute instances delete monolith-server --zone=$ZONE --quiet
```

## 9. Cloud SQL Database

Delete the PostgreSQL instance:

```bash
echo "Removing Cloud SQL instance..."
gcloud sql instances delete $DB_INSTANCE --quiet
```

## 10. Networking (VPC Peering & Firewalls)

Finally, remove the VPC peering connection, the allocated IP range for managed services, and all custom firewall rules:

```bash
echo "Removing VPC peering, IP range, and firewall..."
gcloud services vpc-peerings delete \
  --service=servicenetworking.googleapis.com \
  --network=default --quiet

gcloud compute addresses delete google-managed-services-default \
  --global --quiet

gcloud compute firewall-rules delete allow-app-3000 --quiet
gcloud compute firewall-rules delete allow-health-checks --quiet
gcloud compute firewall-rules delete allow-http --quiet
```

---

## Verification

To confirm that the key resources have been successfully removed, you can run:

```bash
# Should be empty or not show the deleted resources
gcloud compute instances list
gcloud sql instances list
gcloud redis instances list --region=$REGION
gcloud functions list --region=$REGION
```

## Next steps

Now that you have a clean slate, you're ready to explore containerizing the application. 

- [Tutorial 4.1: Containerization & Cloud Run](../phase4_containers/01_containerization_cloud_run.md) — package the app as a Docker container
