# Cloud Run Function (2nd gen) triggered by Pub/Sub topic: image-upload
# Reads the original image from GCS, generates a 200x200 thumbnail using Pillow,
# and saves it back to GCS under the "thumbnails/" prefix.

import base64
import io
import json

import functions_framework
from google.cloud import storage
from PIL import Image

storage_client = storage.Client()

# Pub/Sub message format (base64-encoded JSON):
# {
#   "imageId": 42,
#   "bucketName": "my-app-images",
#   "filename": "1712345678-photo.jpg",
#   "mimetype": "image/jpeg"
# }


@functions_framework.cloud_event
def generate_thumbnail(cloud_event):
    message_data = cloud_event.data.get('message', {}).get('data')
    if not message_data:
        print('No message data received')
        return

    payload = json.loads(base64.b64decode(message_data).decode('utf-8'))
    image_id = payload['imageId']
    bucket_name = payload['bucketName']
    filename = payload['filename']
    mimetype = payload['mimetype']

    print(f'Processing imageId={image_id}, file={filename}')

    bucket = storage_client.bucket(bucket_name)

    # Download the original image into memory
    image_bytes = bucket.blob(filename).download_as_bytes()

    # Generate 200x200 thumbnail using Pillow (covers the box, maintains quality)
    img = Image.open(io.BytesIO(image_bytes))
    img.thumbnail((200, 200), Image.LANCZOS)

    output = io.BytesIO()
    fmt = 'JPEG' if 'jpeg' in mimetype else 'PNG'
    img.save(output, format=fmt)
    output.seek(0)

    # Upload thumbnail back to GCS
    thumbnail_filename = f'thumbnails/thumb-{filename}'
    dest_blob = bucket.blob(thumbnail_filename)
    dest_blob.upload_from_file(output, content_type=mimetype)

    thumbnail_url = f'https://storage.googleapis.com/{bucket_name}/{thumbnail_filename}'
    print(f'Thumbnail created: {thumbnail_url}')
