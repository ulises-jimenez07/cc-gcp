// v5: Production-ready containerized app.
//     Same logic as v4, hardened for Cloud Run / GKE deployment.
//     All config comes from environment variables (injected by K8s Secrets or Cloud Run).

const express = require('express');
const multer = require('multer');
const mysql = require('mysql2/promise');
const { Storage } = require('@google-cloud/storage');
const { PubSub } = require('@google-cloud/pubsub');
const { createClient } = require('redis');

const app = express();
const PORT = process.env.PORT || 8080; // Cloud Run default port

// --- GCS ---
const storage = new Storage();
const bucket = storage.bucket(process.env.GCS_BUCKET);

// --- Pub/Sub ---
const pubsub = new PubSub();
const TOPIC_NAME = process.env.PUBSUB_TOPIC || 'image-upload';

// --- Redis ---
const redis = createClient({
  socket: { host: process.env.REDIS_HOST || '127.0.0.1', port: 6379 }
});
redis.on('error', (err) => console.error('Redis error:', err));
redis.connect();

// --- Multer ---
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 5 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    if (!file.mimetype.startsWith('image/')) return cb(new Error('Only image files are allowed'));
    cb(null, true);
  }
});

// --- Cloud SQL ---
const pool = mysql.createPool({
  host:     process.env.DB_HOST,
  user:     process.env.DB_USER || 'app_user',
  password: process.env.DB_PASS,
  database: process.env.DB_NAME || 'app_db',
  waitForConnections: true,
  connectionLimit: 10
});

app.use(express.json());

// Kubernetes liveness & readiness probes
app.get('/health', (req, res) => res.json({ status: 'ok', version: 'v5' }));
app.get('/ready', async (req, res) => {
  try {
    await pool.query('SELECT 1');
    res.json({ status: 'ready' });
  } catch (err) {
    res.status(503).json({ status: 'not ready', error: err.message });
  }
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

app.post('/upload', upload.single('image'), async (req, res) => {
  try {
    const { originalname, buffer, size, mimetype } = req.file;
    const filename = `${Date.now()}-${originalname}`;

    await bucket.file(filename).save(buffer, { metadata: { contentType: mimetype }, resumable: false });
    const publicUrl = `https://storage.googleapis.com/${process.env.GCS_BUCKET}/${filename}`;

    const [result] = await pool.query(
      'INSERT INTO images (filename, original_name, url, size, mime_type) VALUES (?, ?, ?, ?, ?)',
      [filename, originalname, publicUrl, size, mimetype]
    );

    await pubsub.topic(TOPIC_NAME).publishMessage({
      data: Buffer.from(JSON.stringify({ imageId: result.insertId, bucketName: process.env.GCS_BUCKET, filename, mimetype }))
    });

    await redis.del('images:all');
    res.status(201).json({ message: 'Uploaded', url: publicUrl });
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

    res.json({ message: 'Deleted' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, shutting down gracefully...');
  await redis.quit();
  await pool.end();
  process.exit(0);
});

app.listen(PORT, '0.0.0.0', () => console.log(`[v5] Server running on port ${PORT}`));
