// v2: identical to v1 in code — the only change is that DB_HOST now points to
// the Cloud SQL instance's Private IP instead of localhost.
// No Cloud SQL Auth Proxy needed because the VM is on the same VPC.

const express = require('express');
const multer = require('multer');
const mysql = require('mysql2/promise');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

// --- Local disk storage (unchanged from v1) ---
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const uploadDir = './uploads';
    if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir);
    cb(null, uploadDir);
  },
  filename: (req, file, cb) => {
    cb(null, `${Date.now()}-${file.originalname}`);
  }
});

const upload = multer({
  storage,
  limits: { fileSize: 5 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    if (!file.mimetype.startsWith('image/')) {
      return cb(new Error('Only image files are allowed'));
    }
    cb(null, true);
  }
});

// --- Cloud SQL connection pool ---
// DB_HOST = Private IP of the Cloud SQL instance (e.g. 10.68.0.3)
// Set via environment variables or a .env file — never hardcode credentials.
const pool = mysql.createPool({
  host:     process.env.DB_HOST,      // Cloud SQL Private IP
  user:     process.env.DB_USER || 'app_user',
  password: process.env.DB_PASS,
  database: process.env.DB_NAME || 'app_db',
  waitForConnections: true,
  connectionLimit: 10
});

app.use(express.json());
app.use('/uploads', express.static('uploads'));

app.get('/health', async (req, res) => {
  try {
    await pool.query('SELECT 1');
    res.json({ status: 'ok', version: 'v2', db: 'cloud-sql' });
  } catch (err) {
    res.status(500).json({ status: 'error', db: err.message });
  }
});

app.get('/images', async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT * FROM images ORDER BY created_at DESC');
    res.json(rows);
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
    const { originalname, filename, size, mimetype } = req.file;
    const url = `/uploads/${filename}`;

    await pool.query(
      'INSERT INTO images (filename, original_name, url, size, mime_type) VALUES (?, ?, ?, ?, ?)',
      [filename, originalname, url, size, mimetype]
    );

    res.status(201).json({ message: 'Image uploaded successfully', url });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.delete('/images/:id', async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT * FROM images WHERE id = ?', [req.params.id]);
    if (rows.length === 0) return res.status(404).json({ error: 'Not found' });

    fs.unlinkSync(`.${rows[0].url}`);
    await pool.query('DELETE FROM images WHERE id = ?', [req.params.id]);

    res.json({ message: 'Image deleted' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => console.log(`[v2] Server running on port ${PORT}`));
