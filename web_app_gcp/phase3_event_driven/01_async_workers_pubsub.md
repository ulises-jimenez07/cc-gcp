# Tutorial 3.1: Async Workers (Pub/Sub & Cloud Run Functions)

Image resizing is CPU-intensive. If the web app generates a thumbnail synchronously on upload, every upload is slow and the VM wastes CPU that should be handling HTTP requests.

**Event-driven architecture** solves this: the web app publishes a lightweight event to a **Pub/Sub topic** and returns immediately. A separate **Cloud Run Function** subscribes to the topic and performs the thumbnail generation in the background.

```
                        Pub/Sub Topic
   Client               "image-upload"
     │                       │
     │  POST /upload          │
     ▼                       │
  Express App (v4) ─publish──▶│──trigger──▶ thumbnail-worker
     │   (fast!)              │              (Cloud Run Function)
     │                        │               1. download original from GCS
     ▼                                        2. resize with sharp (200x200)
  Response: 201                               3. save thumbnail to GCS
  "queued for processing"                         gs://bucket/thumbnails/thumb-...
```

**App version:** `v4`
**Function:** `app/v4/functions/thumbnail-worker/`
**Previous tutorial:** [2.2 CDN with Cloud Storage](../phase2_performance/02_cdn.md)
**Next tutorial:** [4.1 Containerization & Cloud Run](../phase4_containers/01_containerization_cloud_run.md)

---

## 1. Create the Pub/Sub Topic

### Console

1. **Pub/Sub > Topics > Create Topic**
   - **Topic ID**: `image-upload`
   - Leave defaults
2. Click **Create**

### gcloud CLI

```bash
gcloud pubsub topics create image-upload
```

---

## 2. Create a Service Account for the Function

The Cloud Run Function needs permission to read and write objects in GCS.

```bash
PROJECT_ID=$(gcloud config get-value project)

# Create a dedicated service account
gcloud iam service-accounts create thumbnail-worker-sa \
  --display-name="Thumbnail Worker Service Account"

# Grant Storage Object Admin (read originals + write thumbnails)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:thumbnail-worker-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

---

## 3. Deploy the Cloud Run Function

The function code is in [app/v4/functions/thumbnail-worker/](../app/v4/functions/thumbnail-worker/).

### Console

1. **Cloud Run Functions > Create Function**
2. **Environment**: 2nd gen
3. **Function name**: `thumbnail-worker`
4. **Region**: `us-central1`
5. **Trigger type**: Cloud Pub/Sub → select topic `image-upload`
6. **Runtime**: Node.js 18
7. **Entry point**: `generateThumbnail`
8. Upload the source code (or paste from `index.js` and `package.json`)
9. Under **Runtime, build, connections and security settings**:
   - **Service account**: `thumbnail-worker-sa`
   - **Memory**: 512 MB (sharp is memory-intensive)
10. Click **Deploy**

### gcloud CLI

```bash
PROJECT_ID=$(gcloud config get-value project)
BUCKET_NAME=my-app-images-$PROJECT_ID

gcloud functions deploy thumbnail-worker \
  --gen2 \
  --runtime=nodejs18 \
  --region=us-central1 \
  --source=app/v4/functions/thumbnail-worker \
  --entry-point=generateThumbnail \
  --trigger-topic=image-upload \
  --service-account=thumbnail-worker-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --memory=512MB \
  --timeout=60s
```

---

## 4. Update the app to v4

The v4 app ([app/v4/app.js](../app/v4/app.js)) is identical to v3 with one addition: after uploading to GCS and recording in Cloud SQL, it publishes a Pub/Sub message.

The published message format:
```json
{
  "imageId": 42,
  "bucketName": "my-app-images-PROJECT_ID",
  "filename": "1712345678-photo.jpg",
  "mimetype": "image/jpeg"
}
```

Update the app on the VM:

```bash
gcloud compute ssh monolith-server --zone=us-central1-a
```

```bash
cd ~/cc-gcp/app/v4
npm install

# Update systemd service
sudo nano /etc/systemd/system/image-app.service

# Add/update the entry point and env var:
# WorkingDirectory=/home/<YOUR_USER>/cc-gcp/app/v4
# Environment=PUBSUB_TOPIC=image-upload

sudo systemctl daemon-reload
sudo systemctl restart image-app
```

*Note: the VM's service account needs the `roles/pubsub.publisher` role to publish messages.*

```bash
PROJECT_ID=$(gcloud config get-value project)

SA_EMAIL=$(gcloud compute instances describe monolith-server \
  --zone=us-central1-a \
  --format='get(serviceAccounts[0].email)')

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/pubsub.publisher"
```

---

## 5. Test end-to-end

```bash
LB_IP=<YOUR_LB_IP>
BUCKET_NAME=my-app-images-$(gcloud config get-value project)

# Upload an image
curl -X POST http://$LB_IP/upload \
  -F "image=@photo.jpg"
```

Expected response (returns immediately, before the thumbnail is ready):

```json
{
  "message": "Image uploaded, thumbnail generation queued",
  "url": "https://storage.googleapis.com/BUCKET/1712345678-photo.jpg"
}
```

Wait a few seconds, then check for the thumbnail:

```bash
# List thumbnails directory in GCS
gsutil ls gs://$BUCKET_NAME/thumbnails/

# The thumbnail URL follows the pattern:
# https://storage.googleapis.com/BUCKET/thumbnails/thumb-1712345678-photo.jpg
curl -I https://storage.googleapis.com/$BUCKET_NAME/thumbnails/thumb-1712345678-photo.jpg
# Should return HTTP 200
```

---

## 6. Monitor the function

### Console

**Cloud Run Functions > thumbnail-worker > Logs** — you should see entries like:

```
Processing imageId=42, file=1712345678-photo.jpg
Thumbnail created: https://storage.googleapis.com/...
```

### gcloud CLI

```bash
gcloud functions logs read thumbnail-worker \
  --gen2 \
  --region=us-central1 \
  --limit=20
```

---

## 7. Manually publish a test message

You can test the function without uploading through the app:

```bash
BUCKET_NAME=my-app-images-$(gcloud config get-value project)

# Publish a test Pub/Sub message
gcloud pubsub topics publish image-upload \
  --message='{
    "imageId": 1,
    "bucketName": "'$BUCKET_NAME'",
    "filename": "EXISTING_FILENAME.jpg",
    "mimetype": "image/jpeg"
  }'
```

Replace `EXISTING_FILENAME.jpg` with a file that actually exists in your bucket.

---

## 8. Dead-letter topics (optional)

If the function fails repeatedly (e.g., the source file is missing), Pub/Sub will retry indefinitely. A **dead-letter topic** captures failed messages after a configurable number of retries:

```bash
# Create a dead-letter topic
gcloud pubsub topics create image-upload-dlq

# Create a subscription with dead-lettering
gcloud pubsub subscriptions create image-upload-sub \
  --topic=image-upload \
  --dead-letter-topic=image-upload-dlq \
  --max-delivery-attempts=5
```

---

## 9. What changed

| | Before | After |
|--|--|--|
| Thumbnail generation | Synchronous (blocks upload) | Asynchronous (background) |
| Upload response time | Slow (resize + save) | Fast (< 100ms) |
| Processing failures | Fail the upload | Retry via Pub/Sub, DLQ for inspection |
| Scaling | Tied to web tier | Independent (Cloud Run Functions scale to 0) |

---

## Next steps

- [Tutorial 4.1: Containerization & Cloud Run](../phase4_containers/01_containerization_cloud_run.md) — package the app as a Docker container
