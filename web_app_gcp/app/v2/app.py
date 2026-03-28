# v2: identical logic to v1 — the only change is that DB_HOST now points to
# the Cloud SQL instance's Private IP instead of localhost.
# No Cloud SQL Auth Proxy needed because the VM is on the same VPC.

import os
import time
import re
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
import pymysql
import pymysql.cursors

app = FastAPI()

PORT = int(os.environ.get('PORT', 3000))
UPLOAD_DIR = './uploads'
MAX_SIZE = 5 * 1024 * 1024

os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_db():
    db = pymysql.connect(
        host=os.environ['DB_HOST'],       # Cloud SQL Private IP
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

@app.get('/health')
def health(db = Depends(get_db)):
    try:
        with db.cursor() as cur:
            cur.execute('SELECT 1')
        return {'status': 'ok', 'version': 'v2', 'db': 'cloud-sql'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'error: {str(e)}')

@app.get('/images')
def list_images(db = Depends(get_db)):
    with db.cursor() as cur:
        cur.execute('SELECT * FROM images ORDER BY created_at DESC')
        return cur.fetchall()

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
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, 'wb') as f:
        f.write(data)
    url = f'/uploads/{filename}'

    with db.cursor() as cur:
        cur.execute(
            'INSERT INTO images (filename, original_name, url, size, mime_type) VALUES (%s, %s, %s, %s, %s)',
            (filename, image.filename, url, len(data), image.content_type),
        )

    return {'message': 'Image uploaded successfully', 'url': url}

@app.delete('/images/{image_id}')
def delete_image(image_id: int, db = Depends(get_db)):
    with db.cursor() as cur:
        cur.execute('SELECT * FROM images WHERE id = %s', (image_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Not found')

        try:
            os.remove(f'.{row["url"]}')
        except FileNotFoundError:
            pass

        cur.execute('DELETE FROM images WHERE id = %s', (image_id,))

    return {'message': 'Image deleted'}

@app.get('/uploads/{filename}')
def serve_upload(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail='File not found')
    return FileResponse(file_path)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=PORT)
