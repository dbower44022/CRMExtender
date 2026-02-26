# CRM Extender — Deployment Guide

This guide walks you through deploying CRM Extender to an internal test server running Ubuntu or Debian Linux. It assumes HTTPS access over your local network using a self-signed certificate.

**Audience:** Someone with basic command-line familiarity but limited experience with Docker, web servers, or deployment.

---

## Table of Contents

1. [What You Are Deploying](#1-what-you-are-deploying)
2. [Prerequisites](#2-prerequisites)
3. [Server Preparation](#3-server-preparation)
4. [Get the Code](#4-get-the-code)
5. [Configure Environment Variables](#5-configure-environment-variables)
6. [Generate TLS Certificates](#6-generate-tls-certificates)
7. [Build and Start the Application](#7-build-and-start-the-application)
8. [Create the First User Account](#8-create-the-first-user-account)
9. [Connect a Gmail Account (Optional)](#9-connect-a-gmail-account-optional)
10. [Verify the Deployment](#10-verify-the-deployment)
11. [Day-to-Day Operations](#11-day-to-day-operations)
12. [Troubleshooting](#12-troubleshooting)
13. [Architecture Overview](#13-architecture-overview)
14. [Environment Variable Reference](#14-environment-variable-reference)

---

## 1. What You Are Deploying

CRM Extender is a web application that aggregates email conversations, calendar events, and contacts from Gmail into a unified CRM view. It consists of:

- **A Python backend** (FastAPI) that handles all data processing, API endpoints, and the traditional web UI
- **A React frontend** (single-page application) that provides a modern grid-based interface
- **An SQLite database** that stores all your data in a single file
- **An nginx reverse proxy** that handles HTTPS (encrypted connections)

All of these run inside Docker containers, so you don't need to install Python, Node.js, or nginx directly on the server.

### How the pieces fit together

```
Browser (your computer)
    │
    ▼ HTTPS (port 443)
┌──────────┐
│  nginx   │  ← Handles encryption, forwards traffic
└────┬─────┘
     │ HTTP (port 8000, internal)
     ▼
┌──────────┐
│   app    │  ← Python/FastAPI application
└────┬─────┘
     │
     ▼
┌──────────┐
│  SQLite  │  ← Database file on disk (./data/)
└──────────┘
```

---

## 2. Prerequisites

You will need:

| What                      | Why                              | How to check             |
| ------------------------- | -------------------------------- | ------------------------ |
| An Ubuntu/Debian server   | The machine you're deploying to  | `lsb_release -a`         |
| SSH access to that server | To run commands remotely         | `ssh user@server-ip`     |
| Docker Engine 24+         | Runs the application containers  | `docker --version`       |
| Docker Compose v2         | Orchestrates multiple containers | `docker compose version` |
| Git                       | To download the code             | `git --version`          |
| OpenSSL                   | To generate TLS certificates     | `openssl version`        |

You will also need:

- The **repository URL** for CRM Extender (ask your team lead)
- An **Anthropic API key** (for AI-powered conversation summarization — the app works without it, but AI features will be disabled)
- Optionally, a **Google Cloud OAuth `client_secret.json`** file (needed only if you want to sync Gmail/Calendar data)

---

## 3. Server Preparation

### 3.1 Connect to your server

Open a terminal and SSH into your server:

```bash
ssh your-username@server-ip-address
```

Replace `your-username` with your login name and `server-ip-address` with the server's IP (e.g., `192.168.1.50`).

### 3.2 Install Docker

If Docker is not already installed, run these commands one at a time:

```bash
# Update the package list
sudo apt-get update

# Install prerequisites
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker's repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

> **Note for Debian:** Replace `ubuntu` with `debian` in the repository URL above.

### 3.3 Allow your user to run Docker without sudo

By default, Docker requires `sudo` for every command. This one-time setup removes that requirement:

```bash
sudo usermod -aG docker $USER
```

**You must log out and log back in** for this to take effect:

```bash
exit
ssh your-username@server-ip-address
```

Verify it works:

```bash
docker run hello-world
```

You should see "Hello from Docker!" in the output.

### 3.4 Install Git and OpenSSL (if not present)

```bash
sudo apt-get install -y git openssl
```

---

## 4. Get the Code

### 4.1 Clone the repository

Pick a directory on the server where you want to install CRM Extender. A common choice is your home directory:

```bash
cd ~
git clone <repo-url> CRMExtender
cd CRMExtender
```

Replace `<repo-url>` with the actual repository URL.

### 4.2 Understand the directory layout

After cloning, the important directories are:

```
CRMExtender/
├── poc/                  ← Python application source code
├── frontend/             ← React frontend source code
├── deploy/               ← Deployment configuration files
│   ├── nginx.conf        ← Nginx web server configuration
│   ├── generate-certs.sh ← Script to create TLS certificates
│   └── certs/            ← Where certificates will be stored
├── Dockerfile            ← Instructions to build the app container
├── docker-compose.yml    ← Defines all the containers and how they connect
├── .env.example          ← Template for environment configuration
├── data/                 ← Created automatically — stores the database
└── credentials/          ← For Google OAuth files (if using Gmail sync)
```

---

## 5. Configure Environment Variables

The application reads its configuration from a file called `.env` in the project root. This file contains secrets (like API keys) and should never be committed to git.

### 5.1 Create the .env file

```bash
cp .env.example .env
```

### 5.2 Edit the .env file

Open the file in a text editor:

```bash
nano .env
```

> **nano basics:** Use arrow keys to navigate. Edit text normally. Press `Ctrl+O` then `Enter` to save. Press `Ctrl+X` to exit.

### 5.3 Required settings

At minimum, set these values:

#### SESSION_SECRET_KEY

This is a random string used to secure user sessions. Generate one with:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and paste it as the value:

```
SESSION_SECRET_KEY=paste-the-random-string-here
```

> **Why this matters:** If you leave the default value (`change-me-in-production`), anyone who knows that string could forge login sessions.

#### POC_DB_PATH

Inside the Docker container, the database lives at a specific path. Set:

```
POC_DB_PATH=/app/data/crm_extender.db
```

#### CRM_UPLOAD_DIR

File uploads (note attachments) need a container-relative path too:

```
CRM_UPLOAD_DIR=/app/data/uploads
```

### 5.4 Optional but recommended settings

#### ANTHROPIC_API_KEY

If you have an Anthropic API key and want AI features (conversation summarization, triage):

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

The app works without this — you just won't get AI summaries.

#### CRM_TIMEZONE

Set your display timezone. All data is stored in UTC regardless, but the UI will show times in this timezone:

```
CRM_TIMEZONE=America/New_York
```

Common values: `America/New_York`, `America/Chicago`, `America/Denver`, `America/Los_Angeles`, `Europe/London`, `UTC`

#### CRM_AUTH_ENABLED

Leave this as `true` for any server accessible on a network:

```
CRM_AUTH_ENABLED=true
```

> Only set to `false` for local development where you want to skip the login screen.

### 5.5 Example complete .env file

```
ANTHROPIC_API_KEY=sk-ant-abc123...
SESSION_SECRET_KEY=a1b2c3d4e5f6...long-random-hex-string...
CRM_AUTH_ENABLED=true
CRM_TIMEZONE=America/New_York
POC_DB_PATH=/app/data/crm_extender.db
CRM_UPLOAD_DIR=/app/data/uploads
```

Save and close the file.

---

## 6. Generate TLS Certificates

HTTPS requires a TLS certificate. For an internal test server, a self-signed certificate is fine. Browsers will show a warning the first time, but the connection will still be encrypted.

### 6.1 Run the certificate generator

```bash
bash deploy/generate-certs.sh
```

You should see:

```
Self-signed certificate generated in /path/to/deploy/certs
```

### 6.2 Verify the certificates were created

```bash
ls deploy/certs/
```

You should see two files:

```
server.crt    ← The certificate (public)
server.key    ← The private key (keep this secret)
```

### 6.3 Certificate expiration

The certificate is valid for 365 days. When it expires, just re-run `bash deploy/generate-certs.sh` and restart nginx:

```bash
bash deploy/generate-certs.sh
docker compose restart nginx
```

---

## 7. Build and Start the Application

### 7.1 Build and launch

This single command builds the application from source and starts all containers:

```bash
docker compose up -d --build
```

**What this does, step by step:**

1. **Builds the frontend** — Downloads Node.js dependencies and compiles the React app
2. **Builds the backend** — Installs Python and all required libraries
3. **Starts the app container** — Runs the Python web server
4. **Starts the nginx container** — Runs the HTTPS reverse proxy

The first build takes several minutes (downloading dependencies, compiling). Subsequent builds are much faster because Docker caches unchanged layers.

The `-d` flag means "detached" — the containers run in the background so you can close your terminal.

### 7.2 Verify the containers are running

```bash
docker compose ps
```

You should see two containers with `Up` status:

```
NAME                  IMAGE             STATUS          PORTS
crmextender-app-1     crmextender-app   Up 10 seconds   8000/tcp
crmextender-nginx-1   nginx:alpine      Up 10 seconds   0.0.0.0:80->80, 0.0.0.0:443->443
```

If either container shows `Exited` or `Restarting`, check the logs (see [Troubleshooting](#12-troubleshooting)).

### 7.3 Check the application logs

```bash
docker compose logs app --tail 20
```

You should see a line like:

```
Starting web UI at http://0.0.0.0:8000
```

This means the app started successfully. The database is created automatically on first startup — no manual setup needed.

---

## 8. Create the First User Account

The application requires you to log in. You need to create an admin account before you can use it.

### 8.1 Open the registration page

On a fresh database with no users, the application automatically enables the "Create Account" link on the login page. Open your browser and go to:

```
https://server-ip-address/login
```

You'll see a login form with a **Create Account** link. Click it.

### 8.2 Register the first user

Fill out the registration form:

- **Name** — Your display name
- **Email** — Use a real email address (especially if you plan to connect Gmail later)
- **Password** — Choose a strong password (minimum 8 characters)
- **Confirm Password** — Re-enter the same password

Click **Register**. You will be automatically logged in and redirected to the dashboard.

> **Important:** The first user registered on a fresh database is automatically given the **admin** role. All subsequent registrations (if self-registration remains enabled) create regular users.

### 8.3 Disable self-registration (recommended)

Once your admin account is created, you probably want to disable public registration. You can do this from the web UI:

1. Go to **Settings** (gear icon) > **System**
2. Set **Allow Self-Registration** to **No** / **false**

After this, new user accounts can only be created by an admin through the Settings > Users page.

### 8.4 (Alternative) Create a user via the CLI

If you prefer, you can also create a user from the command line:

```bash
docker compose exec app python -m poc bootstrap-user --password your-password
```

This creates an admin user from an existing Gmail provider account. It only works if a provider account has already been connected (see [Section 9](#9-connect-a-gmail-account-optional)).

---

## 9. Connect a Gmail Account (Optional)

Connecting a Gmail account enables email sync, calendar sync, and outbound email. This step requires a Google Cloud OAuth `client_secret.json` file.

> **Don't have a `client_secret.json`?** You can skip this section entirely. The CRM will work — you just won't have email/calendar integration.

### 9.1 Prerequisites

You need a `client_secret.json` file from Google Cloud Console configured with:

- Gmail API enabled
- Google Calendar API enabled
- Google People API enabled
- OAuth consent screen configured
- OAuth 2.0 credentials created (Desktop application type)

Ask your team lead for this file if you don't have it.

### 9.2 Copy the credentials file to the server

From your local machine:

```bash
scp /path/to/client_secret.json your-username@server-ip:~/CRMExtender/credentials/
```

Or if you have the file locally, you can paste its contents:

```bash
nano ~/CRMExtender/credentials/client_secret.json
# Paste the JSON content, save with Ctrl+O, exit with Ctrl+X
```

### 9.3 Add the Gmail account

#### Option A: Using the Web UI (recommended)

1. Log in to the app at `https://server-ip/app/`
2. Navigate to **Settings** (gear icon) > **Accounts**
3. Click **Add Account**
4. Complete the Google OAuth consent flow in your browser
5. Grant the requested permissions (Gmail read/send, Calendar read, Contacts read)

#### Option B: Using the CLI

This approach opens a browser window for OAuth consent. It works if you have a graphical desktop on the server or use SSH port forwarding.

**With SSH port forwarding** (from your local machine):

```bash
# In a separate terminal, set up the tunnel
ssh -L 8080:localhost:8080 your-username@server-ip

# On the server
docker compose exec app python -m poc add-account
```

A URL will be printed. Open it in your local browser, complete the consent flow, and the CLI will capture the token.

**What happens:** The OAuth flow stores a token file in `./credentials/` on the host (mounted into the container). This token is used for all future Gmail/Calendar API calls.

---

## 10. Verify the Deployment

### 10.1 Test HTTPS connectivity

From the server itself:

```bash
curl -k https://localhost/api/v1/health
```

> The `-k` flag tells curl to accept the self-signed certificate.

You should see a JSON response. If authentication is enabled, you'll see:

```json
{"error": "Authentication required"}
```

This is correct — it means the app is running and reachable through nginx.

### 10.2 Test from a browser

On your local machine, open:

```
https://server-ip-address/
```

> **Browser certificate warning:** You'll see a warning like "Your connection is not private" or "This site's security certificate is not trusted." This is expected with self-signed certificates. Click "Advanced" → "Proceed" (or equivalent) to continue.

You should see the login page. Log in with the credentials you created in [Section 8](#8-create-the-first-user-account).

### 10.3 Verify the React SPA

After logging in, navigate to:

```
https://server-ip-address/app/
```

This is the modern React interface with the grid-based layout.

### 10.4 Verify the database was created

On the server:

```bash
ls -lh data/crm_extender.db
```

You should see a database file (it starts small and grows as you add data).

---

## 11. Day-to-Day Operations

### Starting the application

```bash
cd ~/CRMExtender
docker compose up -d
```

### Stopping the application

```bash
docker compose down
```

This stops and removes the containers. Your data is safe — it's stored in the `./data/` directory on the host, not inside the containers.

### Restarting the application

```bash
docker compose restart
```

Or restart just one service:

```bash
docker compose restart app     # Restart only the Python app
docker compose restart nginx   # Restart only nginx
```

### Updating to the latest code

```bash
cd ~/CRMExtender
git pull
docker compose up -d --build
```

The `--build` flag rebuilds the container images with the new code. Docker layer caching makes this fast if only application code changed (not dependencies).

### Viewing logs

```bash
# All services, last 50 lines, following new output
docker compose logs -f --tail 50

# Just the app
docker compose logs -f app

# Just nginx
docker compose logs -f nginx
```

Press `Ctrl+C` to stop following logs.

### Backing up the database

**Quick backup (requires brief downtime):**

```bash
docker compose stop app
cp ./data/crm_extender.db ./data/crm_extender-backup-$(date +%Y%m%d).db
docker compose start app
```

**Online backup (no downtime):**

```bash
docker compose exec app python3 -c "
import sqlite3
src = sqlite3.connect('/app/data/crm_extender.db')
dst = sqlite3.connect('/app/data/crm_extender-backup.db')
src.backup(dst)
dst.close()
src.close()
print('Backup complete')
"
```

Then copy the backup off the server:

```bash
# From your local machine
scp your-username@server-ip:~/CRMExtender/data/crm_extender-backup.db ./
```

### Opening a shell inside the container

For debugging or running CLI commands:

```bash
docker compose exec app bash
```

Type `exit` to return to the host.

### Checking disk usage

```bash
# Database size
ls -lh data/crm_extender.db

# Total data directory
du -sh data/

# Docker disk usage
docker system df
```

---

## 12. Troubleshooting

### Container won't start

Check the logs for error messages:

```bash
docker compose logs app --tail 50
docker compose logs nginx --tail 50
```

### "Permission denied" on docker commands

Your user isn't in the `docker` group. Run:

```bash
sudo usermod -aG docker $USER
```

Then **log out and log back in**.

### Nginx shows SSL errors

The certificates might be missing or expired. Regenerate them:

```bash
bash deploy/generate-certs.sh
docker compose restart nginx
```

### "Authentication required" on everything

This is normal when `CRM_AUTH_ENABLED=true`. You need to:

1. Create a user account (see [Section 8](#8-create-the-first-user-account))
2. Log in at `https://server-ip/login`

### Cannot reach the server from another machine

1. **Check the server's firewall** allows ports 80 and 443:
   
   ```bash
   sudo ufw status
   ```
   
   If the firewall is active and doesn't list ports 80/443:
   
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   ```

2. **Check the containers are running:**
   
   ```bash
   docker compose ps
   ```

3. **Check nginx is listening:**
   
   ```bash
   curl -k https://localhost/
   ```
   
   If this works locally but not remotely, it's a firewall or network issue.

### Browser says "connection refused"

The containers may not be running. Check:

```bash
docker compose ps
```

If both containers show `Up`, the issue is likely a firewall or that you're using the wrong IP address.

### App starts but shows "may need migration" warning

If upgrading from an older database, you may need to run migrations:

```bash
docker compose exec app python -m poc migrate
```

Check the app logs for the specific migration version needed.

### Docker build fails with "npm ci" errors

This usually means `package-lock.json` is out of sync. On a machine with Node.js installed:

```bash
cd frontend
npm install
# Commit the updated package-lock.json
```

### Out of disk space

Docker images and build cache can consume significant space. Clean up:

```bash
# Remove unused Docker data (safe — only removes stopped containers, unused images, etc.)
docker system prune

# More aggressive — also removes unused images
docker system prune -a
```

### Forgot the admin password

Reset it using the built-in CLI command:

```bash
docker compose exec app python -m poc set-password admin@example.com --password new-password-here
```

Replace `admin@example.com` with the actual email and `new-password-here` with the new password. If you omit `--password`, it will prompt you interactively (with confirmation).

---

## 13. Architecture Overview

### Container architecture

| Container             | Image                   | Purpose                           | Ports                |
| --------------------- | ----------------------- | --------------------------------- | -------------------- |
| `crmextender-app-1`   | Built from `Dockerfile` | Python/FastAPI application server | 8000 (internal only) |
| `crmextender-nginx-1` | `nginx:alpine`          | TLS termination, reverse proxy    | 80, 443 (public)     |

### Data persistence

Data lives on the **host** filesystem, not inside containers. Containers are ephemeral — you can destroy and recreate them without losing data.

| Host path        | Container path      | Contents                                          |
| ---------------- | ------------------- | ------------------------------------------------- |
| `./data/`        | `/app/data/`        | SQLite database, file uploads                     |
| `./credentials/` | `/app/credentials/` | Google OAuth `client_secret.json` and token files |
| `./.env`         | (env_file)          | Environment variables (secrets, configuration)    |

### Why SQLite (not PostgreSQL/MySQL)?

CRM Extender uses SQLite because:

- **Zero configuration** — no separate database server to install, configure, or maintain
- **Single-file backup** — copy one file and you have a complete backup
- **Sufficient for internal use** — SQLite handles thousands of concurrent reads and sequential writes well
- **Single-process app** — the app runs one Python process (uvicorn), so there's no write contention

### Why nginx in front of the app?

- **TLS termination** — the Python app speaks plain HTTP; nginx handles HTTPS
- **Request buffering** — nginx efficiently buffers slow client connections
- **Standard practice** — well-documented, battle-tested approach

### Why not multiple app workers?

SQLite allows only one writer at a time. Multiple Python worker processes would contend for write access, causing "database is locked" errors under load. A single uvicorn process is the right choice for SQLite-backed applications. This is perfectly adequate for an internal test server.

---

## 14. Environment Variable Reference

All configuration is done through environment variables in the `.env` file.

### Required for Production

| Variable             | Default                   | Description                                                                                                                               |
| -------------------- | ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `SESSION_SECRET_KEY` | `change-me-in-production` | Random string for signing session cookies. **Must be changed.** Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `POC_DB_PATH`        | `data/crm_extender.db`    | Path to the SQLite database. Set to `/app/data/crm_extender.db` in Docker.                                                                |
| `CRM_UPLOAD_DIR`     | `data/uploads`            | Directory for file uploads. Set to `/app/data/uploads` in Docker.                                                                         |

### Recommended

| Variable            | Default | Description                                                                           |
| ------------------- | ------- | ------------------------------------------------------------------------------------- |
| `ANTHROPIC_API_KEY` | (empty) | Anthropic API key for AI conversation summarization. App works without it.            |
| `CRM_AUTH_ENABLED`  | `true`  | Set `false` only for local development. Always `true` on a network-accessible server. |
| `CRM_TIMEZONE`      | `UTC`   | Display timezone (IANA format). Data is always stored in UTC.                         |

### Gmail / AI Tuning (Optional)

| Variable                     | Default                    | Description                                      |
| ---------------------------- | -------------------------- | ------------------------------------------------ |
| `POC_GMAIL_QUERY`            | `newer_than:7d`            | Gmail search filter used during sync.            |
| `POC_GMAIL_MAX_THREADS`      | `50`                       | Maximum Gmail threads fetched per sync run.      |
| `POC_CLAUDE_MODEL`           | `claude-sonnet-4-20250514` | Anthropic model used for summarization.          |
| `POC_GMAIL_RATE_LIMIT`       | `5`                        | Gmail API requests per second.                   |
| `POC_CLAUDE_RATE_LIMIT`      | `2`                        | Anthropic API requests per second.               |
| `POC_MAX_CONVERSATION_CHARS` | `6000`                     | Max characters sent to Claude for summarization. |
| `POC_TARGET_CONVERSATIONS`   | `5`                        | Target number of triaged conversations per sync. |

### Session / Upload Limits (Optional)

| Variable                 | Default         | Description                            |
| ------------------------ | --------------- | -------------------------------------- |
| `SESSION_TTL_HOURS`      | `720` (30 days) | How long login sessions remain valid.  |
| `CRM_MAX_UPLOAD_SIZE_MB` | `10`            | Maximum file upload size in megabytes. |

### Google OAuth

Google OAuth credentials are **not** set via environment variables. Instead, place a `client_secret.json` file in the `./credentials/` directory. The app reads the `client_id` and `client_secret` from this JSON file at startup. If the file is absent, Google sign-in and Gmail sync are simply unavailable.
