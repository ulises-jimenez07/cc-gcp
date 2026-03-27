# Tutorial 2.1: Caching for Speed (Memorystore Redis)

As traffic grows, the same database queries run over and over — "list all images" is called on every page load. Without a cache, every request hits Cloud SQL, adding latency and increasing DB load.

In this tutorial you provision a **Memorystore (Redis)** instance and implement the **Cache-Aside** pattern in the app: check Redis first, fall back to Cloud SQL on a miss, then populate the cache for next time.

```
   Client
     │
     ▼
  Express App (v3)
     │
     ├─── GET /images ──▶ Redis (Memorystore)
     │                       │
     │                 ┌─────┴──────┐
     │                 │ cache HIT  │  return immediately (< 1ms)
     │                 │ cache MISS │──▶ Cloud SQL ──▶ populate cache
     │                 └────────────┘
     │
     └─── POST /upload ──▶ GCS ──▶ Cloud SQL ──▶ invalidate cache
```

**App version:** `v3`
**Previous tutorial:** [1.3 Horizontal Scaling](../phase1_monolith/03_horizontal_scaling.md)
**Next tutorial:** [2.2 CDN with Cloud Storage](./02_cdn.md)

---

## 1. The Cache-Aside Pattern

Cache-Aside (also called *lazy loading*) is the most common caching strategy:

1. **On read:** check the cache. If found (HIT), return it. If not (MISS), query the DB, write the result to cache, return it.
2. **On write/delete:** update the DB and **invalidate** (delete) the corresponding cache key.

This ensures the cache is never stale for long and is only populated with data that is actually being requested.

*Note: the TTL (time-to-live) you set on cache entries acts as a safety net — even if an invalidation is missed, the cache will expire on its own.*

---

## 2. Create a Memorystore Redis Instance

The Redis instance must be on the same VPC as your MIG VMs so it's reachable via Private IP.

### Console

1. **Memorystore > Redis > Create Instance**
   - **Instance ID**: `metadata-cache`
   - **Tier**: Basic (for dev/small workloads)
   - **Capacity**: 1 GB
   - **Region**: `us-central1`
   - **Zone**: `us-central1-a`
   - **Connect mode**: Private Service Access (same VPC as your VMs)
2. Click **Create** (takes ~2 minutes)

### gcloud CLI

```bash
gcloud redis instances create metadata-cache \
  --size=1 \
  --region=us-central1 \
  --zone=us-central1-a \
  --redis-version=redis_7_0 \
  --connect-mode=PRIVATE_SERVICE_ACCESS \
  --network=default
```

---

## 3. Get the Redis Private IP

### Console

**Memorystore > Redis > metadata-cache** — note the **Primary endpoint** (e.g., `10.68.1.5:6379`).

### gcloud CLI

```bash
gcloud redis instances describe metadata-cache \
  --region=us-central1 \
  --format='get(host)'
```

---

## 4. Update the app to v3

Switch the app on your VM (or update the Instance Template for the MIG) to `v3`:

```bash
gcloud compute ssh monolith-server --zone=us-central1-a
```

```bash
cd ~/cc-gcp/app/v3
npm install
```

Update the systemd service to add the new env vars:

```bash
sudo tee /etc/systemd/system/image-app.service > /dev/null << 'EOF'
[Unit]
Description=Image App Node.js Service (v3)
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/home/<YOUR_USER>/cc-gcp/app/v3
ExecStart=/usr/bin/node app.js
Restart=on-failure
Environment=PORT=3000
Environment=DB_HOST=<CLOUD_SQL_PRIVATE_IP>
Environment=DB_USER=app_user
Environment=DB_PASS=StrongPassword123!
Environment=DB_NAME=app_db
Environment=GCS_BUCKET=my-app-images
Environment=REDIS_HOST=<MEMORYSTORE_PRIVATE_IP>

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl restart image-app
```

---

## 5. How the Cache-Aside code works

The key logic in `app/v3/app.js`:

```javascript
// GET /images — Cache-Aside
app.get('/images', async (req, res) => {
  const CACHE_KEY = 'images:all';
  const CACHE_TTL = 60; // seconds

  const cached = await redis.get(CACHE_KEY);
  if (cached) {
    return res.json({ source: 'cache', data: JSON.parse(cached) });
  }

  // Cache miss: query the DB
  const [rows] = await pool.query('SELECT * FROM images ORDER BY created_at DESC');

  // Populate cache with 60-second TTL
  await redis.setEx(CACHE_KEY, CACHE_TTL, JSON.stringify(rows));

  res.json({ source: 'db', data: rows });
});

// POST /upload — after writing to DB, invalidate the cache
await redis.del('images:all');
```

---

## 6. Verify caching behavior

```bash
LB_IP=<YOUR_LB_IP>

# First call — cache miss, queries Cloud SQL
curl http://$LB_IP/images
# Response: { "source": "db", "data": [...] }

# Second call — cache hit, returns from Redis instantly
curl http://$LB_IP/images
# Response: { "source": "cache", "data": [...] }

# Upload a new image — invalidates the cache
curl -X POST http://$LB_IP/upload -F "image=@photo.jpg"

# Next call — cache miss again (invalidated), re-queries Cloud SQL
curl http://$LB_IP/images
# Response: { "source": "db", "data": [...] }
```

---

## 7. Connect to Redis directly for debugging

From a VM on the same VPC:

```bash
# Install redis-cli
sudo apt-get install -y redis-tools

REDIS_IP=<MEMORYSTORE_PRIVATE_IP>

redis-cli -h $REDIS_IP ping          # PONG
redis-cli -h $REDIS_IP keys '*'      # list all keys
redis-cli -h $REDIS_IP ttl images:all  # check remaining TTL
redis-cli -h $REDIS_IP get images:all  # see the raw cached JSON
```

---

## 8. What changed

| | v2 | v3 |
|--|--|--|
| Images | Local disk | GCS (see Tutorial 2.2) |
| DB queries on every `/images` | Yes | Only on cache miss |
| Cache TTL | N/A | 60 seconds |
| Cache invalidation | N/A | On upload and delete |

---

## Next steps

- [Tutorial 2.2: CDN with Cloud Storage](./02_cdn.md) — fix the local disk storage problem and serve images from edge locations
