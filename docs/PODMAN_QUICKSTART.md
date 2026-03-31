# Podman Quickstart Guide — KYC Platform

This guide covers every command needed to run the KYC Platform with **Podman** on
Windows, Linux, or macOS.
All orchestration is handled by `manage.py` at the project root — no docker-compose needed.

---

## Prerequisites

### Install Podman

**Windows (recommended: Podman Desktop)**
```powershell
# Option A — Podman Desktop (includes GUI + CLI)
winget install RedHat.Podman-Desktop

# Option B — CLI only via winget
winget install RedHat.Podman

# Option C — Scoop
scoop install podman
```

**macOS**
```bash
brew install podman
podman machine init
podman machine start
```

**Linux (Fedora / RHEL / CentOS)**
```bash
sudo dnf install podman
```

**Linux (Ubuntu / Debian)**
```bash
sudo apt-get update
sudo apt-get install -y podman
```

Verify:
```bash
podman --version   # should print podman version 4.x or 5.x
```

---

## 1. First-Time Setup

```bash
# Clone / navigate to the project
cd "c:/Users/venkat.s.boddula/OneDrive - Accenture/SynOps2.0/Repo/KYC"

# The .env file is already present with development defaults.
# Edit the secrets you actually need (OpenAI key, Gmail password, etc.):
notepad .env          # Windows
# nano .env           # Linux / macOS
```

Key values to set in `.env` before running:

| Variable | What to fill in |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI key from platform.openai.com |
| `GOOGLE_API_KEY` | Your Gemini key from aistudio.google.com |
| `SMTP_USER` / `SMTP_PASSWORD` | Gmail account + App Password (optional) |
| `SECRET_KEY` | Run `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_SECRET_KEY` | Same command as above, different value |

---

## 2. Start Everything

```bash
# Build backend image + pull base images + start all services + run migrations
python manage.py up

# Skip rebuilding images (faster on subsequent starts)
python manage.py up --no-build

# Also start pgAdmin (database GUI on http://localhost:5050)
python manage.py up --pgadmin

# Start only specific services
python manage.py up postgres redis
```

The `up` command:
1. Pulls `postgres:16-alpine`, `redis:7-alpine`, `pgadmin4`
2. Builds `localhost/kyc_backend:latest` from `backend/Dockerfile`
3. Creates named volumes (`kyc_postgres_data`, `kyc_redis_data`, etc.)
4. Creates the **`kyc_pod`** (all containers share one network namespace)
5. Starts containers in dependency order
6. Waits for PostgreSQL + Redis to be healthy
7. Runs `alembic upgrade head` automatically
8. Waits for the FastAPI backend to respond

**Service URLs after `up`:**

| Service | URL |
|---|---|
| Backend API | http://localhost:8000 |
| Swagger / API Docs | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Frontend (dev) | http://localhost:3000 |
| Flower (Celery UI) | http://localhost:5555 |
| pgAdmin | http://localhost:5050 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

## 3. Stop Everything

```bash
# Stop all containers and remove the pod (volumes are preserved)
python manage.py down

# Stop a specific service only
python manage.py down backend
```

---

## 4. View Logs

```bash
# Last 100 lines from all services
python manage.py logs

# Follow logs in real time (Ctrl+C to exit)
python manage.py logs -f

# Logs for a specific service, last 200 lines
python manage.py logs backend --tail 200

# Follow logs for multiple services
python manage.py logs backend celery_worker -f
```

---

## 5. Check Status

```bash
# Show pod + all container states
python manage.py status

# Check HTTP health endpoints
python manage.py health
```

---

## 6. Rebuild After Code Changes

```bash
# Rebuild only the backend image (fastest)
python manage.py build backend

# Rebuild + restart the backend container
python manage.py build backend && python manage.py restart backend

# Full rebuild + restart everything
python manage.py down && python manage.py up
```

---

## 7. Database Operations

```bash
# Run pending Alembic migrations (applies all revisions including 004_admin_workflow)
python manage.py migrate

# Check current revision
python manage.py shell
# Inside container: alembic current

# Open psql interactive shell
python manage.py psql

# Inside psql:
# \dt              — list tables (includes kyc_workflow_steps, kyc_final_reports,
#                                  kyc_admin_decisions, kyc_timeline)
# \d kyc_workflow_steps  — describe workflow steps table
# \d kyc_final_reports   — describe final reports table
# SELECT * FROM users LIMIT 5;
# \q               — quit
```

---

## 8. Shell Access

```bash
# Open bash inside the backend container
python manage.py shell

# Open bash in a specific container
python manage.py shell postgres
python manage.py shell redis

# Once inside the backend container you can run:
# alembic history
# alembic current
# python -c "from app.core.config import settings; print(settings.DATABASE_URL)"
```

---

## 9. Restart Services

```bash
# Restart all services
python manage.py restart

# Restart only the backend (after a code change with --no-build)
python manage.py restart backend

# Restart celery worker
python manage.py restart celery_worker
```

---

## 10. Full Cleanup

```bash
# Remove all containers, the pod, AND all volumes (wipes all data)
python manage.py clean

# Skip the confirmation prompt
python manage.py clean --yes
```

---

## Manual Podman Commands (Reference)

The following are the raw Podman commands that `manage.py` runs internally.
Useful for debugging or if you prefer direct control.

### Pod

```bash
# Create the pod with all required port mappings
podman pod create \
  --name kyc_pod \
  --hostname kyc-platform \
  -p 5432:5432 \
  -p 6379:6379 \
  -p 8000:8000 \
  -p 3000:3000 \
  -p 5555:5555 \
  -p 5050:80

# List pods
podman pod ls

# Stop and remove the pod (also stops all containers inside it)
podman pod stop kyc_pod
podman pod rm -f kyc_pod
```

### Named Volumes

```bash
# Create all required volumes
podman volume create kyc_postgres_data
podman volume create kyc_redis_data
podman volume create kyc_uploads_data
podman volume create kyc_logs_data

# List volumes
podman volume ls

# Inspect a volume (see its mount path)
podman volume inspect kyc_postgres_data

# Remove a volume
podman volume rm kyc_postgres_data
```

### PostgreSQL Container

```bash
podman run -d \
  --pod kyc_pod \
  --name kyc_postgres \
  --restart unless-stopped \
  -e POSTGRES_DB=kyc_db \
  -e POSTGRES_USER=kyc_user \
  -e POSTGRES_PASSWORD=KycPgPass2025! \
  -e PGDATA=/var/lib/postgresql/data/pgdata \
  -v kyc_postgres_data:/var/lib/postgresql/data \
  docker.io/library/postgres:16-alpine

# Check it is ready
podman exec kyc_postgres pg_isready -U kyc_user -d kyc_db
```

### Redis Container

```bash
podman run -d \
  --pod kyc_pod \
  --name kyc_redis \
  --restart unless-stopped \
  -v kyc_redis_data:/data \
  docker.io/library/redis:7-alpine \
  redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru

# Ping Redis
podman exec kyc_redis redis-cli ping   # → PONG
```

### Build & Start Backend

```bash
# Build the image
podman build \
  --target production \
  -t localhost/kyc_backend:latest \
  -f backend/Dockerfile \
  backend/

# Run backend
podman run -d \
  --pod kyc_pod \
  --name kyc_backend \
  --restart unless-stopped \
  --env-file .env \
  -e DATABASE_URL="postgresql+asyncpg://kyc_user:KycPgPass2025!@localhost:5432/kyc_db" \
  -e REDIS_URL="redis://localhost:6379/0" \
  -e CELERY_BROKER_URL="redis://localhost:6379/1" \
  -e CELERY_RESULT_BACKEND="redis://localhost:6379/2" \
  -v kyc_uploads_data:/app/uploads \
  -v kyc_logs_data:/app/logs \
  localhost/kyc_backend:latest

# Run migrations
podman exec kyc_backend alembic upgrade head
```

### Celery Worker

```bash
podman run -d \
  --pod kyc_pod \
  --name kyc_celery_worker \
  --restart unless-stopped \
  --env-file .env \
  -e DATABASE_URL="postgresql+asyncpg://kyc_user:KycPgPass2025!@localhost:5432/kyc_db" \
  -e CELERY_BROKER_URL="redis://localhost:6379/1" \
  -e CELERY_RESULT_BACKEND="redis://localhost:6379/2" \
  -v kyc_uploads_data:/app/uploads \
  -v kyc_logs_data:/app/logs \
  localhost/kyc_backend:latest \
  celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4 -Q kyc_tasks,document_tasks
```

### Celery Beat (Scheduler)

```bash
podman run -d \
  --pod kyc_pod \
  --name kyc_celery_beat \
  --restart unless-stopped \
  --env-file .env \
  -e CELERY_BROKER_URL="redis://localhost:6379/1" \
  -e CELERY_RESULT_BACKEND="redis://localhost:6379/2" \
  localhost/kyc_backend:latest \
  celery -A app.tasks.celery_app beat --loglevel=info
```

### Flower (Celery Monitoring)

```bash
podman run -d \
  --pod kyc_pod \
  --name kyc_flower \
  --restart unless-stopped \
  -e CELERY_BROKER_URL="redis://localhost:6379/1" \
  -e CELERY_RESULT_BACKEND="redis://localhost:6379/2" \
  localhost/kyc_backend:latest \
  celery -A app.tasks.celery_app flower --port=5555
```

### pgAdmin (Optional)

```bash
podman run -d \
  --pod kyc_pod \
  --name kyc_pgadmin \
  --restart unless-stopped \
  -e PGADMIN_DEFAULT_EMAIL=admin@kyc-platform.com \
  -e PGADMIN_DEFAULT_PASSWORD=PgAdmin2025! \
  docker.io/dpage/pgadmin4:latest
```

---

## Inspecting the Pod

```bash
# Full pod details (JSON)
podman pod inspect kyc_pod

# All containers in the pod
podman ps -a --filter pod=kyc_pod

# Resource usage
podman pod stats kyc_pod

# Container logs
podman logs kyc_backend
podman logs -f kyc_celery_worker   # follow
```

---

## Export as Kubernetes YAML (Optional)

Podman can generate a Kubernetes-compatible pod YAML from the running pod:

```bash
podman generate kube kyc_pod > kyc_pod.yaml
```

This can be applied to a Kubernetes or OpenShift cluster:

```bash
kubectl apply -f kyc_pod.yaml
# or
podman play kube kyc_pod.yaml
```

---

## Troubleshooting

### Port already in use
```bash
# Find what is using port 5432
netstat -ano | findstr :5432          # Windows
lsof -i :5432                          # macOS / Linux

# Kill it (Windows)
taskkill /PID <pid> /F
```

### Backend fails to connect to PostgreSQL
Inside the pod all containers share `localhost`. Check the `DATABASE_URL` in `.env` uses `localhost` (not `postgres` like a docker-compose setup).

```bash
# Test the connection from inside the backend container
podman exec kyc_backend python -c \
  "import asyncio, asyncpg; asyncio.run(asyncpg.connect('postgresql://kyc_user:KycPgPass2025!@localhost:5432/kyc_db'))"
```

### Podman machine not running (macOS / Windows)
```bash
podman machine list
podman machine start
```

### Reset everything
```bash
python manage.py clean --yes
podman system prune -a --volumes
```
