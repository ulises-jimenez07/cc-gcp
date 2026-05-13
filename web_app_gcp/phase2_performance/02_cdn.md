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
   - Cache mode: **Cache static content (CACHE_ALL_STATIC)**
3. **Routing rules**: Add a new rule:
   - Match: path prefix `/storage/*`
   - Route to: `img-backend-bucket`
   - **Path rewrite (URL rewrite):** set **Path prefix rewrite** to `/`
     > This strips the `/storage` prefix before forwarding to GCS. Without it, GCS receives `/storage/filename.jpg` as the object key, but the object is stored as `filename.jpg`.
4. Click **Save**

### gcloud CLI

```bash
PROJECT_ID=$(gcloud config get-value project)
BUCKET_NAME=my-app-images-$(gcloud config get-value project)

# Create the backend bucket with CDN enabled
gcloud compute backend-buckets create img-backend-bucket \
  --gcs-bucket-name=$BUCKET_NAME \
  --enable-cdn \
  --cache-mode=CACHE_ALL_STATIC

# Add a path matcher with path rewrite to the URL map
# Note: unquoted EOF is required so $PROJECT_ID is expanded before being passed to gcloud
gcloud compute url-maps import app-url-map --global << EOF
defaultService: https://www.googleapis.com/compute/v1/projects/$PROJECT_ID/global/backendServices/app-backend
name: app-url-map
hostRules:
- hosts:
  - '*'
  pathMatcher: app-paths
pathMatchers:
- name: app-paths
  defaultService: https://www.googleapis.com/compute/v1/projects/$PROJECT_ID/global/backendServices/app-backend
  pathRules:
  - paths:
    - /storage/*
    service: https://www.googleapis.com/compute/v1/projects/$PROJECT_ID/global/backendBuckets/img-backend-bucket
    routeAction:
      urlRewrite:
        pathPrefixRewrite: /
EOF
```

*Note: the simpler approach is to use the Console to edit the URL map — the import format can be complex.*

---

## 3. Verify CDN is working

Upload a new image and request it via the load balancer URL:

```bash
LB_IP=$(gcloud compute forwarding-rules describe app-forwarding-rule --global --format='get(IPAddress)')
BUCKET_NAME=my-app-images-$(gcloud config get-value project)

# Download a test image and upload it, capturing the JSON response
curl -L -o /tmp/demo-photo.jpg https://picsum.photos/1024/768
UPLOAD_JSON=$(curl -s -X POST http://$LB_IP/upload -F "image=@/tmp/demo-photo.jpg")
echo "$UPLOAD_JSON"
# e.g.: {"message":"Image uploaded successfully","url":"https://storage.googleapis.com/my-app-images-PROJECT_ID/1712345678901-demo-photo.jpg"}

# Extract the object name (the app uses millisecond timestamps, so expect 13 digits)
FILENAME=$(echo "$UPLOAD_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['url'].split('/')[-1])")
echo "Object name: $FILENAME"

# Verify the object exists directly in GCS before testing CDN routing
# A 200 here confirms the object was uploaded and the bucket is public.
# A 403/404 means the upload failed or the bucket is not publicly readable (see Tutorial 2.1 §4).
curl -s -o /dev/null -w "Direct GCS status: %{http_code}\n" \
  https://storage.googleapis.com/$BUCKET_NAME/$FILENAME

# First request via LB: full GET to populate the CDN cache
curl -o /dev/null -D - http://$LB_IP/storage/$FILENAME

# Second request: cache hit — look for the Age header
curl -o /dev/null -D - http://$LB_IP/storage/$FILENAME
```

> **Why `curl -o /dev/null -D -` and not `curl -I`?**  
> `-I` sends a HEAD request. Cloud CDN may not populate the cache on HEAD requests. Use a full GET (`-o /dev/null` discards the body, `-D -` prints headers to stdout) to guarantee the object is cached.

On the **second request**, look for the `Age` header — it shows how many seconds the response has been sitting in the CDN cache:

```
Age: 12
Cache-Control: public, max-age=3600
```

> **Why no `x-goog-cache-status`?**  
> That header only appears on the newer **Global External HTTP(S) Load Balancer**. This tutorial uses a **Classic** load balancer, which does not inject it. The CDN is still working — use the `Age` header or Cloud Logging (below) to confirm.

### Confirm via Cloud Logging

The most reliable way to verify CDN hits on Classic LB:

```
resource.type="http_load_balancer"
jsonPayload.cacheId!=""
```

A log entry with `"statusDetails": "response_from_cache"` and `"cacheHit": true` confirms the CDN is serving the object from the edge.

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
      "condition": { "age": 30 }
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
