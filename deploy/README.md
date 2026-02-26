# CRM Extender — Deployment Guide

Deploy CRM Extender to an internal test server with Docker Compose and HTTPS.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- Git
- OpenSSL (for generating self-signed certificates)

## 1. Clone & Configure

```bash
git clone <repo-url> CRMExtender
cd CRMExtender
cp .env.example .env
```

Edit `.env` with your values:

```
ANTHROPIC_API_KEY=sk-ant-...          # Required for AI features
SESSION_SECRET_KEY=<random-string>    # Generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
CRM_AUTH_ENABLED=true
CRM_TIMEZONE=America/New_York         # Or your timezone
POC_DB_PATH=/app/data/crm_extender.db
CRM_UPLOAD_DIR=/app/data/uploads
```

## 2. Generate Self-Signed Certificates

```bash
bash deploy/generate-certs.sh
```

This creates `deploy/certs/server.crt` and `deploy/certs/server.key`.

## 3. Build & Launch

```bash
docker compose up -d --build
```

Verify both containers are running:

```bash
docker compose ps
docker compose logs app     # Should show "Starting web UI at http://0.0.0.0:8000"
```

## 4. Bootstrap First User

```bash
docker compose exec app python -m poc bootstrap-user \
    --email admin@example.com \
    --password <your-password>
```

## 5. Google OAuth Setup (Provider Accounts)

To add a Gmail provider account for email sync, you need Google OAuth credentials.

### Option A: Web UI (recommended for headless servers)

1. Place your `client_secret.json` in the `./credentials/` directory on the host
2. Log in to the web UI at `https://<server-ip>/app/`
3. Go to Settings > Accounts > Add Account
4. Complete the OAuth consent flow in your browser

### Option B: CLI (requires browser access)

If you can open a browser on the server (or use SSH port forwarding):

```bash
# Copy client_secret.json into the container's credentials volume
cp /path/to/client_secret.json ./credentials/

# Run add-account (opens a browser for OAuth consent)
docker compose exec app python -m poc add-account
```

For headless servers without browser access, use SSH port forwarding:

```bash
ssh -L 8080:localhost:8080 user@server
# Then run add-account from the server
```

## 6. Verify Deployment

```bash
# Health check
curl -k https://localhost/api/v1/health

# Check database was created
ls -la ./data/crm_extender.db
```

Open in browser:
- `https://<server-ip>/` — HTMX web UI (login page)
- `https://<server-ip>/app/` — React SPA

## Ongoing Operations

### Update to Latest Code

```bash
git pull
docker compose up -d --build
```

### View Logs

```bash
docker compose logs -f app      # Application logs
docker compose logs -f nginx    # Nginx access/error logs
```

### Backup Database

```bash
# Stop the app to ensure consistency
docker compose stop app
cp ./data/crm_extender.db ./data/crm_extender-backup-$(date +%Y%m%d).db
docker compose start app
```

Or use SQLite's online backup (no downtime):

```bash
docker compose exec app python3 -c "
import sqlite3, shutil
src = sqlite3.connect('/app/data/crm_extender.db')
dst = sqlite3.connect('/app/data/backup.db')
src.backup(dst)
dst.close()
src.close()
"
```

### Restart Services

```bash
docker compose restart        # Restart all
docker compose restart app    # Restart just the app
```

### Shell Access

```bash
docker compose exec app bash
```
