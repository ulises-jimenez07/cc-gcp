// v4: After a successful upload to GCS, publish a message to Pub/Sub.
//     A Cloud Run Function (thumbnail-worker) subscribes and generates a thumbnail.

const express = require('express');
const multer = require('multer');
const mysql = require('mysql2/promise');
const { Storage } = require('@google-cloud/storage');
const { PubSub } = require('@google-cloud/pubsub');
const { createClient } = require('redis');

const app = express();
const PORT = process.env.PORT || 3000;

// --- GCS client ---
const storage = new Storage();
const bucket = storage.bucket(process.env.GCS_BUCKET);

// --- Pub/Sub client ---
const pubsub = new PubSub();
const TOPIC_NAME = process.env.PUBSUB_TOPIC || 'image-upload';

// --- Redis client ---
const redis = createClient({
  socket: { host: process.env.REDIS_HOST || '127.0.0.1', port: 6379 }
});
redis.on('error', (err) => console.error('Redis error:', err));
redis.connect();

// --- Multer: in-memory storage to stream to GCS ---
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 5 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    if (!file.mimetype.startsWith('image/')) {
      return cb(new Error('Only image files are allowed'));
    }
    cb(null, true);
  }
});

// --- Cloud SQL connection pool ---
const pool = mysql.createPool({
  host:     process.env.DB_HOST,
  user:     process.env.DB_USER || 'app_user',
  password: process.env.DB_PASS,
  database: process.env.DB_NAME || 'app_db',
  waitForConnections: true,
  connectionLimit: 10
});

app.use(express.json());

app.get('/health', async (req, res) => {
  res.json({ status: 'ok', version: 'v4' });
});

// Cache-Aside: list images
app.get('/images', async (req, res) => {
  const CACHE_KEY = 'images:all';
  try {
    const cached = await redis.get(CACHE_KEY);
    if (cached) return res.json({ source: 'cache', data: JSON.parse(cached) });

    const [rows] = await pool.query('SELECT * FROM images ORDER BY created_at DESC');
    await redis.setEx(CACHE_KEY, 60, JSON.stringify(rows));
    res.json({ source: 'db', data: rows });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/images/:id', async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT * FROM images WHERE id = ?', [req.params.id]);
    if (rows.length === 0) return res.status(404).json({ error: 'Not found' });
    res.json(rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Upload: store in GCS → record in DB → publish event
app.post('/upload', upload.single('image'), async (req, res) => {
  try {
    const { originalname, buffer, size, mimetype } = req.file;
    const filename = `${Date.now()}-${originalname}`;
    const gcsFile = bucket.file(filename);

    // 1. Upload to GCS
    await gcsFile.save(buffer, { metadata: { contentType: mimetype }, resumable: false });
    const publicUrl = `https://storage.googleapis.com/${process.env.GCS_BUCKET}/${filename}`;

    // 2. Record metadata in Cloud SQL
    const [result] = await pool.query(
      'INSERT INTO images (filename, original_name, url, size, mime_type) VALUES (?, ?, ?, ?, ?)',
      [filename, originalname, publicUrl, size, mimetype]
    );

    // 3. Publish event so thumbnail-worker can process the image asynchronously
    const message = {
      imageId:    result.insertId,
      bucketName: process.env.GCS_BUCKET,
      filename,
      mimetype
    };
    await pubsub.topic(TOPIC_NAME).publishMessage({
      data: Buffer.from(JSON.stringify(message))
    });

    // 4. Invalidate list cache
    await redis.del('images:all');

    res.status(201).json({ message: 'Image uploaded, thumbnail generation queued', url: publicUrl });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.delete('/images/:id', async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT * FROM images WHERE id = ?', [req.params.id]);
    if (rows.length === 0) return res.status(404).json({ error: 'Not found' });

    await bucket.file(rows[0].filename).delete();
    await pool.query('DELETE FROM images WHERE id = ?', [req.params.id]);
    await redis.del('images:all');

    res.json({ message: 'Image deleted' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => console.log(`[v4] Server running on port ${PORT}`));
