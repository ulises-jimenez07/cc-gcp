# Tutorial 2.2: Content Delivery Network (CDN)

Images are now stored in Cloud Storage (GCS) — set up in [Tutorial 2.1](./01_caching_memorystore.md). But they're still served from a single origin in `us-central1`, so users far away experience high latency.

In this tutorial you enable **Cloud CDN** on the GCS bucket so images are cached at Google's edge nodes worldwide.

```mermaid
graph TD
    User(["User (São Paulo)"]) --> CDN["Cloud CDN Edge\n(Google PoP)"]
    CDN -- "cache HIT < 10ms" --> User
    CDN -- "cache MISS" --> GCS["Cloud Storage Bucket\n(GCS Backend Bucket)\nserved from us-central1"]
    App["FastAPI App (v3)"] -- "POST /upload\nstreams files to GCS" --> GCS
```

**App version:** `v3` (deployed in Tutorial 2.1)
**Previous tutorial:** [2.1 Caching with Memorystore](./01_caching_memorystore.md)
**Next tutorial:** [3.1 Async Workers](../phase3_event_driven/01_async_workers_pubsub.md)

---

## 1. Verify GCS uploads are working

Before enabling CDN, confirm the v3 app is uploading to GCS correctly.

```bash
LB_IP=$(gcloud compute forwarding-rules describe app-forwarding-rule --global --format='get(IPAddress)')
BUCKET_NAME=my-app-images-$(gcloud config get-value project)

curl -X POST http://$LB_IP/upload \
  -F "image=@/path/to/photo.jpg"
```

The response should include a GCS URL:

```json
{
  "message": "Image uploaded successfully",
  "url": "https://storage.googleapis.com/my-app-images-PROJECT_ID/1712345678-photo.jpg"
}
```

If uploads fail, check that the service account was granted `Storage Object Admin` on the bucket (covered in [Tutorial 2.1 §5d](./01_caching_memorystore.md#5d-grant-the-vms-service-account-access-to-gcs)).

---

## 2. Add a Backend Bucket to the Load Balancer

To serve GCS files through the load balancer (and enable CDN), add a **Backend Bucket** alongside your existing Backend Service.

### Console

1. **Network Services > Load Balancing > app-url-map > Edit**
2. **Backend configuration > Add Backend > Backend Bucket**
   - Name: `img-backend-bucket`
   - Cloud Storage bucket: `my-app-images-PROJECT_ID`
   - Check **Enable Cloud CDN**
   - Cache mode: **Cache static content**
3. **Routing rules**: Add a new rule:
   - Match: path prefix `/images/storage/*`
   - Route to: `img-backend-bucket`
4. Click **Save**

### gcloud CLI

```bash
BUCKET_NAME=my-app-images-$(gcloud config get-value project)

# Create the backend bucket with CDN enabled
gcloud compute backend-buckets create img-backend-bucket \
  --gcs-bucket-name=$BUCKET_NAME \
  --enable-cdn \
  --cache-mode=CACHE_ALL_STATIC

# Add a path matcher to the URL map
gcloud compute url-maps import app-url-map --global << 'EOF'
defaultService: https://www.googleapis.com/compute/v1/projects/PROJECT_ID/global/backendServices/app-backend
name: app-url-map
hostRules:
- hosts:
  - '*'
  pathMatcher: app-paths
pathMatchers:
- name: app-paths
  defaultService: https://www.googleapis.com/compute/v1/projects/PROJECT_ID/global/backendServices/app-backend
  pathRules:
  - paths:
    - /storage/*
    service: https://www.googleapis.com/compute/v1/projects/PROJECT_ID/global/backendBuckets/img-backend-bucket
EOF
```

*Note: the simpler approach is to use the Console to edit the URL map — the import format can be complex.*

---

## 3. Verify CDN is working

Upload a new image and request it via the load balancer URL:

```bash
LB_IP=$(gcloud compute forwarding-rules describe app-forwarding-rule --global --format='get(IPAddress)')
BUCKET_NAME=my-app-images-$(gcloud config get-value project)

# Upload
curl -X POST http://$LB_IP/upload -F "image=@photo.jpg"
# Note the returned GCS URL, e.g.: https://storage.googleapis.com/BUCKET/filename.jpg

# Access via CDN (first request — cache miss, served from GCS)
curl -I https://storage.googleapis.com/$BUCKET_NAME/filename.jpg
```

Look for the `x-goog-cache-status` header:
- `MISS` on the first request (fetched from GCS and cached at the edge)
- `HIT` on subsequent requests (served from the nearest CDN node)

---

## 4. Storage classes and lifecycle

For images that aren't accessed frequently, reduce storage costs with a lifecycle rule:

```bash
BUCKET_NAME=my-app-images-$(gcloud config get-value project)

# Move objects not accessed in 30 days to Nearline storage
cat > lifecycle.json << 'EOF'
{
  "rule": [
    {
      "action": { "type": "SetStorageClass", "storageClass": "NEARLINE" },
      "condition": { "daysSinceLastContainedInActiveMigration": 30 }
    }
  ]
}
EOF

gsutil lifecycle set lifecycle.json gs://$BUCKET_NAME
```

---

## 5. What changed

| | Before (v3 without CDN) | After (v3 + CDN) |
|--|--|--|
| Image serving | From GCS origin (`us-central1`) | From CDN edge nodes (nearest PoP) |
| Latency (global users) | High | Low |
| Bandwidth cost | GCS egress | CDN (typically cheaper) |

---

## Next steps

- [Tutorial 3.1: Async Workers (Pub/Sub & Functions)](../phase3_event_driven/01_async_workers_pubsub.md) — offload thumbnail generation to a background worker
