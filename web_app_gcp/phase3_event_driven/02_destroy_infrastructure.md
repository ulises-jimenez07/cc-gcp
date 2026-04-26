# Tutorial 3.2: Destroy Compute Infrastructure

In Phase 4 (Containerization), we will move away from Virtual Machines (VMs) and the infrastructure we've built so far to focus exclusively on container-based deployments using Google Kubernetes Engine (GKE) and Cloud Run.

To save costs while preparing for the next phase, we will clean up ONLY the compute-heavy infrastructure (VMs, Load Balancers) that we no longer need. We will KEEP our stateful backends (Cloud SQL, Memorystore, Cloud Storage, Pub/Sub, and Cloud Functions) as our Phase 4 containers will connect to them.

> **NOTE**: This deletes the VMs, Managed Instance Groups, Instance Templates, and the HTTP(S) Load Balancer. It intentionally preserves your database and caches.

---

## 1. Set environment variables

Set the necessary variables to identify the resources to delete:

```bash
ZONE=us-central1-a
```

## 2. Load Balancer

Remove the global HTTP load balancer, its components, and the static IP:

```bash
echo "Removing load balancer..."
gcloud compute forwarding-rules delete app-forwarding-rule --global --quiet || true
gcloud compute target-http-proxies delete app-http-proxy --quiet || true
gcloud compute url-maps delete app-url-map --quiet || true
gcloud compute backend-services delete app-backend --global --quiet || true
gcloud compute addresses delete app-lb-ip --global --quiet || true
gcloud compute backend-buckets delete img-backend-bucket --quiet || true
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

## 5. Monolith VM

Delete the original `monolith-server` VM we used to build and configure the application manually:

```bash
echo "Removing monolith-server VM..."
gcloud compute instances delete monolith-server --zone=$ZONE --quiet
```

## 6. Custom Machine Images

Delete the custom VM images we created during the updates. These consume storage space and cost money:

```bash
echo "Removing custom machine images..."
gcloud compute images delete app-v4-image --quiet || true
gcloud compute images delete app-v3-image --quiet || true
gcloud compute images delete app-v2-image --quiet || true
gcloud compute images delete app-v1-image --quiet || true
```

## 7. Firewall Rules

Delete the firewall rules created for the VMs and Health Checks:

```bash
echo "Removing firewall rules..."
gcloud compute firewall-rules delete allow-app-3000 --quiet || true
gcloud compute firewall-rules delete allow-health-checks --quiet || true
```

---

## Verification

To confirm that the key resources have been successfully removed, you can run:

```bash
# Should only show the stateful resources, with no VMs left
gcloud compute instances list
```

## Next steps

Now that you have a clean slate, you're ready to explore containerizing the application. 

- [Tutorial 4.1: Containerization & Cloud Run](../phase4_containers/01_containerization_cloud_run.md) — package the app as a Docker container
