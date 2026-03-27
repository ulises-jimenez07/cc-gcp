// v3: Images are streamed directly to GCS.
//     Image metadata list is cached in Memorystore Redis (Cache-Aside pattern).

const express = require('express');
const multer = require('multer');
const mysql = require('mysql2/promise');
const { Storage } = require('@google-cloud/storage');
const { createClient } = require('redis');

const app = express();
const PORT = process.env.PORT || 3000;

// --- GCS client ---
const storage = new Storage();
const bucket = storage.bucket(process.env.GCS_BUCKET); // e.g. "my-app-images"

// --- Redis client (Memorystore) ---
const redis = createClient({
  socket: {
    host: process.env.REDIS_HOST || '127.0.0.1',
    port: 6379
  }
});
redis.on('error', (err) => console.error('Redis error:', err));
redis.connect();

// --- Multer: store in memory so we can stream to GCS ---
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

// Health check
app.get('/health', async (req, res) => {
  try {
    await pool.query('SELECT 1');
    await redis.ping();
    res.json({ status: 'ok', version: 'v3', db: 'cloud-sql', cache: 'memorystore', storage: 'gcs' });
  } catch (err) {
    res.status(500).json({ status: 'error', detail: err.message });
  }
});

// --- Cache-Aside: list images ---
// 1. Check Redis for cached result.
// 2. On cache miss, query Cloud SQL and populate the cache.
app.get('/images', async (req, res) => {
  const CACHE_KEY = 'images:all';
  const CACHE_TTL = 60; // seconds

  try {
    const cached = await redis.get(CACHE_KEY);
    if (cached) {
      return res.json({ source: 'cache', data: JSON.parse(cached) });
    }

    const [rows] = await pool.query('SELECT * FROM images ORDER BY created_at DESC');
    await redis.setEx(CACHE_KEY, CACHE_TTL, JSON.stringify(rows));
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

// --- Upload: stream file buffer to GCS, record URL in Cloud SQL, invalidate cache ---
app.post('/upload', upload.single('image'), async (req, res) => {
  try {
    const { originalname, buffer, size, mimetype } = req.file;
    const filename = `${Date.now()}-${originalname}`;
    const gcsFile = bucket.file(filename);

    await gcsFile.save(buffer, {
      metadata: { contentType: mimetype },
      resumable: false
    });

    const publicUrl = `https://storage.googleapis.com/${process.env.GCS_BUCKET}/${filename}`;

    await pool.query(
      'INSERT INTO images (filename, original_name, url, size, mime_type) VALUES (?, ?, ?, ?, ?)',
      [filename, originalname, publicUrl, size, mimetype]
    );

    // Invalidate the list cache so the next GET reflects the new image
    await redis.del('images:all');

    res.status(201).json({ message: 'Image uploaded successfully', url: publicUrl });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// --- Delete: remove from GCS, Cloud SQL, and invalidate cache ---
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

app.listen(PORT, () => console.log(`[v3] Server running on port ${PORT}`));
