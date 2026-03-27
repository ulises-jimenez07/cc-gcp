const express = require('express');
const multer = require('multer');
const mysql = require('mysql2/promise');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

// --- Local disk storage via multer ---
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
  limits: { fileSize: 5 * 1024 * 1024 }, // 5 MB
  fileFilter: (req, file, cb) => {
    if (!file.mimetype.startsWith('image/')) {
      return cb(new Error('Only image files are allowed'));
    }
    cb(null, true);
  }
});

// --- MariaDB / MySQL connection pool ---
const pool = mysql.createPool({
  host:     process.env.DB_HOST || 'localhost',
  user:     process.env.DB_USER || 'app_user',
  password: process.env.DB_PASS || 'password',
  database: process.env.DB_NAME || 'app_db',
  waitForConnections: true,
  connectionLimit: 10
});

app.use(express.json());
app.use('/uploads', express.static('uploads'));

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', version: 'v1' });
});

// List all images
app.get('/images', async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT * FROM images ORDER BY created_at DESC');
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get single image metadata
app.get('/images/:id', async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT * FROM images WHERE id = ?', [req.params.id]);
    if (rows.length === 0) return res.status(404).json({ error: 'Not found' });
    res.json(rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Upload an image
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

// Delete an image
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

app.listen(PORT, () => console.log(`[v1] Server running on port ${PORT}`));
