# v5: Production-ready containerized app.
#     Same logic as v4, hardened for Cloud Run / GKE deployment.
#     All config comes from environment variables (injected by K8s Secrets or Cloud Run).

import os
import io
import time
import json
import re
import signal
import sys
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException
import pymysql
import pymysql.cursors
from google.cloud import storage as gcs_lib
from google.cloud import pubsub_v1
import redis as redis_lib

app = FastAPI()

PORT = int(os.environ.get('PORT', 8080))  # Cloud Run default port
MAX_SIZE = 5 * 1024 * 1024

# --- GCS ---
gcs = gcs_lib.Client()
bucket = gcs.bucket(os.environ.get('GCS_BUCKET', ''))

# --- Pub/Sub ---
publisher = pubsub_v1.PublisherClient()
TOPIC_NAME = os.environ.get('PUBSUB_TOPIC', 'image-upload')

# --- Redis ---
redis = redis_lib.Redis(
    host=os.environ.get('REDIS_HOST', '127.0.0.1'),
    port=6379,
    decode_responses=True,
)

CACHE_KEY = 'images:all'

def get_db():
    db = pymysql.connect(
        host=os.environ['DB_HOST'],
        user=os.environ.get('DB_USER', 'app_user'),
        password=os.environ['DB_PASS'],
        database=os.environ.get('DB_NAME', 'app_db'),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
    try:
        yield db
    finally:
        db.close()

def secure_filename(filename: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)


# Kubernetes liveness & readiness probes
@app.get('/health')
def health():
    return {'status': 'ok', 'version': 'v5'}

@app.get('/ready')
def ready(db = Depends(get_db)):
    try:
        with db.cursor() as cur:
            cur.execute('SELECT 1')
        return {'status': 'ready'}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"not ready: {str(e)}")

@app.get('/images')
def list_images(db = Depends(get_db)):
    cached = redis.get(CACHE_KEY)
    if cached:
        return {'source': 'cache', 'data': json.loads(cached)}

    with db.cursor() as cur:
        cur.execute('SELECT * FROM images ORDER BY created_at DESC')
        rows = cur.fetchall()

    redis.setex(CACHE_KEY, 60, json.dumps(rows, default=str))
    return {'source': 'db', 'data': rows}

@app.get('/images/{image_id}')
def get_image(image_id: int, db = Depends(get_db)):
    with db.cursor() as cur:
        cur.execute('SELECT * FROM images WHERE id = %s', (image_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Not found')
        return row

@app.post('/upload', status_code=201)
async def upload(image: UploadFile = File(...), db = Depends(get_db)):
    if not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail='Only image files are allowed')

    data = await image.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=400, detail='File too large (max 5 MB)')

    filename = f'{int(time.time() * 1000)}-{secure_filename(image.filename)}'
    
    blob = bucket.blob(filename)
    blob.upload_from_file(io.BytesIO(data), content_type=image.content_type)
    public_url = f'https://storage.googleapis.com/{os.environ["GCS_BUCKET"]}/{filename}'

    with db.cursor() as cur:
        cur.execute(
            'INSERT INTO images (filename, original_name, url, size, mime_type) VALUES (%s, %s, %s, %s, %s)',
            (filename, image.filename, public_url, len(data), image.content_type),
        )
        image_id = cur.lastrowid

    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', '')
    topic_path = publisher.topic_path(project_id, TOPIC_NAME)
    publisher.publish(topic_path, json.dumps({
        'imageId': image_id,
        'bucketName': os.environ['GCS_BUCKET'],
        'filename': filename,
        'mimetype': image.content_type,
    }).encode('utf-8'))

    redis.delete(CACHE_KEY)
    return {'message': 'Uploaded', 'url': public_url}

@app.delete('/images/{image_id}')
def delete_image(image_id: int, db = Depends(get_db)):
    with db.cursor() as cur:
        cur.execute('SELECT * FROM images WHERE id = %s', (image_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Not found')

        bucket.blob(row['filename']).delete()
        cur.execute('DELETE FROM images WHERE id = %s', (image_id,))

    redis.delete(CACHE_KEY)
    return {'message': 'Deleted'}

# Graceful shutdown
def _shutdown(signum, frame):
    print('Shutting down gracefully...')
    redis.close()
    sys.exit(0)

signal.signal(signal.SIGTERM, _shutdown)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=PORT)
