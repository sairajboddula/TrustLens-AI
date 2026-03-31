#!/usr/bin/env python3
"""
KYC Platform - Podman Management Script
========================================
Replaces docker-compose with native Podman pod + container management.

All services run inside a single Podman pod (kyc_pod), which means they
share one network namespace and can reach each other via localhost — just
like containers in a docker-compose setup.

Usage
-----
    python manage.py up                    # Build images + start all services
    python manage.py up --no-build         # Start without rebuilding images
    python manage.py down                  # Stop and remove containers
    python manage.py restart [service]     # Restart one or all services
    python manage.py logs [service] [-f]   # View logs (optionally follow)
    python manage.py status                # Show running containers
    python manage.py build [service]       # Build container image(s)
    python manage.py migrate               # Run Alembic DB migrations
    python manage.py shell                 # Open bash inside backend container
    python manage.py psql                  # Open psql inside postgres container
    python manage.py clean                 # Remove pod, containers, volumes
    python manage.py health                # Check service health endpoints
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.resolve()
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
ENV_FILE = ROOT / ".env"

# ---------------------------------------------------------------------------
# ANSI colour helpers (work on Windows with ANSI enabled)
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    os.system("color")  # enable VT sequences on Windows terminal
    # Force UTF-8 output so Unicode symbols (➜ ✔ ✖ ⚠) encode correctly
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"


def _c(colour: str, text: str) -> str:
    return f"{colour}{text}{RESET}"


def info(msg: str) -> None:
    print(_c(CYAN, f"  ➜  {msg}"))


def ok(msg: str) -> None:
    print(_c(GREEN, f"  ✔  {msg}"))


def warn(msg: str) -> None:
    print(_c(YELLOW, f"  ⚠  {msg}"))


def err(msg: str) -> None:
    print(_c(RED, f"  ✖  {msg}"), file=sys.stderr)


def header(msg: str) -> None:
    width = 60
    print()
    print(_c(BOLD + BLUE, "═" * width))
    print(_c(BOLD + BLUE, f"  {msg}"))
    print(_c(BOLD + BLUE, "═" * width))


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def load_env() -> dict[str, str]:
    """Load .env file into a dict (does NOT modify os.environ)."""
    env: dict[str, str] = {}
    if not ENV_FILE.exists():
        warn(f".env not found at {ENV_FILE}. Using defaults.")
        return env
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


ENV = load_env()


def e(key: str, default: str = "") -> str:
    """Get a value from the loaded .env, falling back to os.environ then default."""
    return ENV.get(key) or os.environ.get(key, default)


# ---------------------------------------------------------------------------
# Podman helpers
# ---------------------------------------------------------------------------

PODMAN = shutil.which("podman") or "podman"
POD_NAME = "kyc_pod"
NETWORK_NAME = "kyc_network"


def run(
    args: list[str],
    *,
    check: bool = True,
    capture: bool = False,
    cwd: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    """Run a shell command, optionally raising on failure."""
    cmd_str = " ".join(str(a) for a in args)
    info(f"$ {cmd_str}")
    return subprocess.run(
        args,
        check=check,
        capture_output=capture,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


def podman(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return run([PODMAN, *args], **kwargs)


def container_exists(name: str) -> bool:
    r = podman("container", "exists", name, check=False, capture=True)
    return r.returncode == 0


def container_running(name: str) -> bool:
    r = podman(
        "inspect", name,
        "--format", "{{.State.Running}}",
        check=False, capture=True,
    )
    return r.returncode == 0 and r.stdout.strip() == "true"


def pod_exists() -> bool:
    r = podman("pod", "exists", POD_NAME, check=False, capture=True)
    return r.returncode == 0


def image_exists(tag: str) -> bool:
    r = podman("image", "exists", tag, check=False, capture=True)
    return r.returncode == 0


# ---------------------------------------------------------------------------
# Service definitions
# ---------------------------------------------------------------------------

@dataclass
class Service:
    name: str                        # container name
    image: str                       # image to pull or build tag
    build_context: Optional[Path]    # None → pre-built image, no build step
    build_target: str = "production"
    ports: list[str] = field(default_factory=list)   # "host:container"
    env: dict[str, str] = field(default_factory=dict)
    volumes: list[str] = field(default_factory=list) # "vol_name:/container/path"
    command: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    health_url: str = ""


def _pg_url() -> str:
    user = e("POSTGRES_USER", "kyc_user")
    pw = e("POSTGRES_PASSWORD", "KycPgPass2025!")
    host = "localhost"        # inside the pod all containers share localhost
    port = e("POSTGRES_PORT", "5432")
    db = e("POSTGRES_DB", "kyc_db")
    return f"postgresql+asyncpg://{user}:{pw}@{host}:{port}/{db}"


def _redis_url(db: int = 0) -> str:
    pw = e("REDIS_PASSWORD", "")
    host = "localhost"
    port = e("REDIS_PORT", "6379")
    auth = f":{pw}@" if pw else ""
    return f"redis://{auth}{host}:{port}/{db}"


SERVICES: dict[str, Service] = {
    # ------------------------------------------------------------------
    # PostgreSQL
    # ------------------------------------------------------------------
    "postgres": Service(
        name="kyc_postgres",
        image="docker.io/library/postgres:16-alpine",
        build_context=None,
        ports=[f"{e('POSTGRES_PORT','5432')}:5432"],
        env={
            "POSTGRES_DB": e("POSTGRES_DB", "kyc_db"),
            "POSTGRES_USER": e("POSTGRES_USER", "kyc_user"),
            "POSTGRES_PASSWORD": e("POSTGRES_PASSWORD", "KycPgPass2025!"),
            "PGDATA": "/var/lib/postgresql/data/pgdata",
        },
        volumes=["kyc_postgres_data:/var/lib/postgresql/data"],
        health_url="",
    ),
    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    "redis": Service(
        name="kyc_redis",
        image="docker.io/library/redis:7-alpine",
        build_context=None,
        ports=[f"{e('REDIS_PORT','6379')}:6379"],
        command=[
            "redis-server",
            "--requirepass", e("REDIS_PASSWORD", ""),
            "--maxmemory", "256mb",
            "--maxmemory-policy", "allkeys-lru",
            "--appendonly", "yes",
            "--appendfsync", "everysec",
        ] if e("REDIS_PASSWORD") else [
            "redis-server",
            "--maxmemory", "256mb",
            "--maxmemory-policy", "allkeys-lru",
        ],
        volumes=["kyc_redis_data:/data"],
        health_url="",
    ),
    # ------------------------------------------------------------------
    # Backend (FastAPI)
    # ------------------------------------------------------------------
    "backend": Service(
        name="kyc_backend",
        image="localhost/kyc_backend:latest",
        build_context=BACKEND_DIR,
        build_target="production",
        ports=[f"{e('PORT','8000')}:8000"],
        env={
            "DATABASE_URL": _pg_url(),
            "REDIS_URL": _redis_url(0),
            "CELERY_BROKER_URL": _redis_url(1),
            "CELERY_RESULT_BACKEND": _redis_url(2),
        },
        volumes=[
            "kyc_uploads_data:/app/uploads",
            "kyc_logs_data:/app/logs",
        ],
        depends_on=["postgres", "redis"],
        health_url=f"http://localhost:{e('PORT','8000')}/health",
    ),
    # ------------------------------------------------------------------
    # Celery Worker
    # ------------------------------------------------------------------
    "celery_worker": Service(
        name="kyc_celery_worker",
        image="localhost/kyc_backend:latest",
        build_context=None,  # reuses backend image
        command=[
            "celery", "-A", "app.tasks.celery_app",
            "worker", "--loglevel=info", "--concurrency=4",
            "-Q", "default,kyc_processing,notifications",
        ],
        env={
            "DATABASE_URL": _pg_url(),
            "REDIS_URL": _redis_url(0),
            "CELERY_BROKER_URL": _redis_url(1),
            "CELERY_RESULT_BACKEND": _redis_url(2),
        },
        volumes=[
            "kyc_uploads_data:/app/uploads",
            "kyc_logs_data:/app/logs",
        ],
        depends_on=["postgres", "redis", "backend"],
    ),
    # ------------------------------------------------------------------
    # Celery Beat (Scheduler)
    # ------------------------------------------------------------------
    "celery_beat": Service(
        name="kyc_celery_beat",
        image="localhost/kyc_backend:latest",
        build_context=None,
        command=[
            "celery", "-A", "app.tasks.celery_app",
            "beat", "--loglevel=info",
        ],
        env={
            "DATABASE_URL": _pg_url(),
            "REDIS_URL": _redis_url(0),
            "CELERY_BROKER_URL": _redis_url(1),
            "CELERY_RESULT_BACKEND": _redis_url(2),
        },
        volumes=["kyc_logs_data:/app/logs"],
        depends_on=["postgres", "redis", "backend"],
    ),
    # ------------------------------------------------------------------
    # Flower (Celery UI)
    # ------------------------------------------------------------------
    "flower": Service(
        name="kyc_flower",
        image="localhost/kyc_backend:latest",
        build_context=None,
        command=[
            "celery", "-A", "app.tasks.celery_app",
            "flower", "--port=5555",
        ],
        ports=["5555:5555"],
        env={
            "CELERY_BROKER_URL": _redis_url(1),
            "CELERY_RESULT_BACKEND": _redis_url(2),
        },
        depends_on=["redis"],
        health_url="http://localhost:5555",
    ),
    # ------------------------------------------------------------------
    # Frontend (Vite + React)
    # ------------------------------------------------------------------
    "frontend": Service(
        name="kyc_frontend",
        image="localhost/kyc_frontend:latest",
        build_context=FRONTEND_DIR,
        build_target="production",
        ports=["3000:3000"],
        env={
            "VITE_API_URL": e("VITE_API_URL", "http://localhost:8000/api/v1"),
            "VITE_APP_NAME": e("VITE_APP_NAME", "KYC Platform"),
        },
        depends_on=["backend"],
        health_url="http://localhost:3000",
    ),
    # ------------------------------------------------------------------
    # pgAdmin
    # ------------------------------------------------------------------
    "pgadmin": Service(
        name="kyc_pgadmin",
        image="docker.io/dpage/pgadmin4:latest",
        build_context=None,
        ports=["5050:80"],
        env={
            "PGADMIN_DEFAULT_EMAIL": e("PGADMIN_EMAIL", "admin@kyc-platform.com"),
            "PGADMIN_DEFAULT_PASSWORD": e("PGADMIN_PASSWORD", "PgAdmin2025!"),
        },
        depends_on=["postgres"],
        health_url="http://localhost:5050",
    ),
}

# Services started by default with `up`; pgadmin is opt-in
DEFAULT_SERVICES = [
    "postgres", "redis", "backend",
    "celery_worker", "celery_beat", "flower",
    "frontend",
]


# ---------------------------------------------------------------------------
# Volume management
# ---------------------------------------------------------------------------

VOLUMES = [
    "kyc_postgres_data",
    "kyc_redis_data",
    "kyc_uploads_data",
    "kyc_logs_data",
]


def ensure_volumes() -> None:
    for vol in VOLUMES:
        r = podman("volume", "exists", vol, check=False, capture=True)
        if r.returncode != 0:
            podman("volume", "create", vol)
            ok(f"Volume created: {vol}")
        else:
            info(f"Volume already exists: {vol}")


# ---------------------------------------------------------------------------
# Pod management
# ---------------------------------------------------------------------------

def _pod_port_args() -> list[str]:
    """Collect all port mappings from all default services for pod creation."""
    ports: list[str] = []
    seen: set[str] = set()
    for svc_name in DEFAULT_SERVICES:
        svc = SERVICES[svc_name]
        for p in svc.ports:
            if p not in seen:
                ports += ["-p", p]
                seen.add(p)
    # pgadmin optional but add its port anyway so the pod can expose it
    for p in SERVICES["pgadmin"].ports:
        if p not in seen:
            ports += ["-p", p]
            seen.add(p)
    return ports


def create_pod() -> None:
    if pod_exists():
        info(f"Pod '{POD_NAME}' already exists.")
        return
    port_args = _pod_port_args()
    podman(
        "pod", "create",
        "--name", POD_NAME,
        "--hostname", "kyc-platform",
        *port_args,
    )
    ok(f"Pod '{POD_NAME}' created.")


def remove_pod() -> None:
    if not pod_exists():
        info(f"Pod '{POD_NAME}' does not exist — nothing to remove.")
        return
    podman("pod", "stop", POD_NAME, check=False)
    podman("pod", "rm", "-f", POD_NAME, check=False)
    ok(f"Pod '{POD_NAME}' removed.")


# ---------------------------------------------------------------------------
# Container lifecycle
# ---------------------------------------------------------------------------

def _env_args(env: dict[str, str]) -> list[str]:
    args: list[str] = []
    # Merge parsed .env values (quotes already stripped) with service-specific overrides
    merged = {**ENV, **env}
    for k, v in merged.items():
        if v:  # skip empty values
            args += ["-e", f"{k}={v}"]
    return args


def _volume_args(volumes: list[str]) -> list[str]:
    args: list[str] = []
    for v in volumes:
        args += ["-v", v]
    return args


def start_service(svc_name: str, service: Service) -> None:
    """Start a single service container inside the pod."""
    cname = service.name
    if container_running(cname):
        info(f"{svc_name}: running — stopping to apply latest config.")
        podman("stop", cname, check=False)
    if container_exists(cname):
        info(f"{svc_name}: removing old container.")
        podman("rm", "-f", cname, check=False)

    cmd = [
        "run", "-d",
        "--pod", POD_NAME,
        "--name", cname,
        "--restart", "unless-stopped",
    ]

    cmd += _env_args(service.env)
    cmd += _volume_args(service.volumes)

    if service.command:
        cmd += [service.image, *service.command]
    else:
        cmd.append(service.image)

    podman(*cmd)
    ok(f"{svc_name}: started ({cname})")


def stop_service(svc_name: str) -> None:
    svc = SERVICES.get(svc_name)
    if not svc:
        err(f"Unknown service: {svc_name}")
        return
    cname = svc.name
    if container_running(cname):
        podman("stop", cname, check=False)
        ok(f"{svc_name}: stopped")
    else:
        info(f"{svc_name}: not running")
    if container_exists(cname):
        podman("rm", "-f", cname, check=False)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_backend(target: str = "production") -> None:
    header("Building backend image")
    podman(
        "build",
        "--target", target,
        "-t", "localhost/kyc_backend:latest",
        "-f", str(BACKEND_DIR / "Dockerfile"),
        str(BACKEND_DIR),
    )
    ok("Backend image built: localhost/kyc_backend:latest")


def build_frontend(target: str = "production") -> None:
    header("Building frontend image")
    vite_api = e("VITE_API_URL", "http://localhost:8000/api/v1")
    podman(
        "build",
        "--target", target,
        "-t", "localhost/kyc_frontend:latest",
        "--build-arg", f"VITE_API_URL={vite_api}",
        "--build-arg", f"VITE_APP_NAME={e('VITE_APP_NAME', 'KYC Platform')}",
        "-f", str(FRONTEND_DIR / "Dockerfile"),
        str(FRONTEND_DIR),
    )
    ok("Frontend image built: localhost/kyc_frontend:latest")


def pull_base_images() -> None:
    base_images = [
        "docker.io/library/postgres:16-alpine",
        "docker.io/library/redis:7-alpine",
        "docker.io/dpage/pgadmin4:latest",
    ]
    for img in base_images:
        if not image_exists(img):
            info(f"Pulling {img} ...")
            podman("pull", img)
        else:
            info(f"Image already present: {img}")


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

def wait_for_postgres(timeout: int = 60) -> bool:
    """Poll postgres until it accepts connections."""
    user = e("POSTGRES_USER", "kyc_user")
    db = e("POSTGRES_DB", "kyc_db")
    deadline = time.time() + timeout
    info("Waiting for PostgreSQL to be ready...")
    while time.time() < deadline:
        r = podman(
            "exec", "kyc_postgres",
            "pg_isready", "-U", user, "-d", db,
            check=False, capture=True,
        )
        if r.returncode == 0:
            ok("PostgreSQL is ready.")
            return True
        time.sleep(2)
    err("PostgreSQL did not become ready in time.")
    return False


def wait_for_redis(timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    info("Waiting for Redis to be ready...")
    while time.time() < deadline:
        r = podman(
            "exec", "kyc_redis",
            "redis-cli", "ping",
            check=False, capture=True,
        )
        if r.returncode == 0 and "PONG" in r.stdout:
            ok("Redis is ready.")
            return True
        time.sleep(2)
    err("Redis did not become ready in time.")
    return False


def wait_for_backend(timeout: int = 90) -> bool:
    import urllib.request
    import urllib.error
    port = e("PORT", "8000")
    url = f"http://localhost:{port}/health"
    deadline = time.time() + timeout
    info(f"Waiting for backend at {url} ...")
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    ok("Backend is ready.")
                    return True
        except Exception:
            pass
        time.sleep(3)
    err("Backend did not become ready in time.")
    return False


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_build(args: argparse.Namespace) -> None:
    header("Building images")
    services = args.services or ["backend", "frontend"]
    if "backend" in services or not args.services:
        build_backend()
    if "frontend" in services or not args.services:
        build_frontend()


def cmd_up(args: argparse.Namespace) -> None:
    header("Starting KYC Platform")

    if not ENV_FILE.exists():
        warn(".env file not found. Run: cp .env.example .env  (and fill in secrets)")
        sys.exit(1)

    # 1. Pull / build images
    if not args.no_build:
        pull_base_images()
        build_backend()
        build_frontend()

    # 2. Ensure named volumes exist
    ensure_volumes()

    # 3. Create the pod (all port bindings live here)
    create_pod()

    # 4. Determine which services to start
    target_services = args.services or DEFAULT_SERVICES

    # 5. Start infrastructure first, then app services
    ordered = [s for s in ["postgres", "redis"] if s in target_services]
    ordered += [s for s in target_services if s not in ordered]

    for svc_name in ordered:
        svc = SERVICES.get(svc_name)
        if not svc:
            warn(f"Unknown service '{svc_name}' — skipping.")
            continue
        start_service(svc_name, svc)

    # 6. Wait for infrastructure
    if "postgres" in ordered:
        wait_for_postgres()

    if "redis" in ordered:
        wait_for_redis()

    # 7. Run migrations automatically
    if "backend" in ordered and not args.no_migrate:
        time.sleep(3)  # brief pause for backend process to start
        cmd_migrate(args)
        cmd_seed(args)

    # 8. Wait for backend
    if "backend" in ordered:
        wait_for_backend()

    # 9. Print access info
    header("KYC Platform is running")
    port = e("PORT", "8000")
    print(f"""
  {_c(GREEN, '✔')} Backend API   → {_c(CYAN, f'http://localhost:{port}')}
  {_c(GREEN, '✔')} API Docs      → {_c(CYAN, f'http://localhost:{port}/docs')}
  {_c(GREEN, '✔')} Frontend      → {_c(CYAN, 'http://localhost:3000')}
  {_c(GREEN, '✔')} Flower (tasks)→ {_c(CYAN, 'http://localhost:5555')}
  {_c(GREEN, '✔')} pgAdmin       → {_c(CYAN, 'http://localhost:5050')}  (run with --pgadmin)
  {_c(GREEN, '✔')} PostgreSQL    → {_c(CYAN, 'localhost:5432')}
  {_c(GREEN, '✔')} Redis         → {_c(CYAN, 'localhost:6379')}

  Stop with: {_c(YELLOW, 'python manage.py down')}
  Logs with: {_c(YELLOW, 'python manage.py logs [service] -f')}
""")


def cmd_down(args: argparse.Namespace) -> None:
    header("Stopping KYC Platform")
    services = args.services or list(reversed(DEFAULT_SERVICES)) + ["pgadmin"]
    for svc_name in services:
        stop_service(svc_name)
    remove_pod()
    ok("All services stopped.")


def cmd_restart(args: argparse.Namespace) -> None:
    header("Restarting services")
    services = args.services or DEFAULT_SERVICES
    for svc_name in services:
        svc = SERVICES.get(svc_name)
        if not svc:
            warn(f"Unknown service: {svc_name}")
            continue
        stop_service(svc_name)
        start_service(svc_name, svc)


def cmd_logs(args: argparse.Namespace) -> None:
    services = args.services or DEFAULT_SERVICES
    for svc_name in services:
        svc = SERVICES.get(svc_name)
        if not svc:
            warn(f"Unknown service: {svc_name}")
            continue
        log_cmd = ["logs"]
        if args.follow:
            log_cmd.append("-f")
        if args.tail:
            log_cmd += ["--tail", str(args.tail)]
        log_cmd.append(svc.name)
        podman(*log_cmd, check=False)


def cmd_status(args: argparse.Namespace) -> None:
    header("KYC Platform Status")
    podman("pod", "ps", "--filter", f"name={POD_NAME}", check=False)
    print()
    podman(
        "ps", "-a",
        "--filter", f"pod={POD_NAME}",
        "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}",
        check=False,
    )


def cmd_migrate(args: argparse.Namespace) -> None:
    header("Running database migrations")
    if not container_running("kyc_backend"):
        err("Backend container is not running. Start with: python manage.py up")
        sys.exit(1)
    # Pass env vars explicitly so alembic sees unquoted values regardless of
    # how the container was originally started.
    svc = SERVICES["backend"]
    exec_env = _env_args(svc.env)  # returns ['-e', 'KEY=VAL', ...]
    podman(
        "exec", *exec_env, "kyc_backend",
        "alembic", "upgrade", "head",
    )
    ok("Migrations complete.")


def cmd_shell(args: argparse.Namespace) -> None:
    svc_name = args.service or "backend"
    svc = SERVICES.get(svc_name)
    if not svc:
        err(f"Unknown service: {svc_name}")
        sys.exit(1)
    if not container_running(svc.name):
        err(f"'{svc_name}' is not running.")
        sys.exit(1)
    os.execvp(PODMAN, [PODMAN, "exec", "-it", svc.name, "/bin/bash"])


def cmd_psql(args: argparse.Namespace) -> None:
    if not container_running("kyc_postgres"):
        err("PostgreSQL is not running.")
        sys.exit(1)
    user = e("POSTGRES_USER", "kyc_user")
    db = e("POSTGRES_DB", "kyc_db")
    os.execvp(PODMAN, [PODMAN, "exec", "-it", "kyc_postgres", "psql", "-U", user, "-d", db])


def cmd_health(args: argparse.Namespace) -> None:
    import urllib.request
    import urllib.error
    header("Health Checks")
    checks = {
        "Backend API": f"http://localhost:{e('PORT','8000')}/health",
        "Flower":      "http://localhost:5555",
        "pgAdmin":     "http://localhost:5050",
    }
    for name, url in checks.items():
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                status = resp.status
                colour = GREEN if status < 400 else RED
                print(f"  {_c(colour, '●')} {name:<20} {_c(colour, str(status))}  {url}")
        except Exception as exc:
            print(f"  {_c(RED, '●')} {name:<20} {_c(RED, 'UNREACHABLE')}  ({exc})")


def cmd_seed(args: argparse.Namespace) -> None:
    header("Seeding demo users")
    if not container_running("kyc_backend"):
        err("Backend container is not running. Start with: python manage.py up")
        sys.exit(1)

    # Copy the seed script into the container in case image was built before it existed
    seed_src = BACKEND_DIR / "seed_demo_users.py"
    if seed_src.exists():
        podman("cp", str(seed_src), "kyc_backend:/app/seed_demo_users.py", check=False)

    svc = SERVICES["backend"]
    exec_env = _env_args(svc.env)
    podman(
        "exec", *exec_env, "kyc_backend",
        "python", "/app/seed_demo_users.py",
    )
    ok("Demo users seeded.")
    print()
    print("  Admin:  admin@kyc.com  /  Admin@KYC2024!")
    print("  User:   user@kyc.com   /  User@KYC2024!")


def cmd_clean(args: argparse.Namespace) -> None:
    header("Cleaning up ALL KYC resources")
    if not args.yes:
        answer = input(_c(YELLOW, "  This will DELETE all containers AND volumes. Continue? [y/N] "))
        if answer.lower() not in ("y", "yes"):
            info("Aborted.")
            return
    remove_pod()
    for vol in VOLUMES:
        r = podman("volume", "exists", vol, check=False, capture=True)
        if r.returncode == 0:
            podman("volume", "rm", vol, check=False)
            ok(f"Volume removed: {vol}")
    ok("Clean complete.")


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="manage.py",
        description="KYC Platform — Podman management script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # up
    p_up = sub.add_parser("up", help="Build images and start all services")
    p_up.add_argument("services", nargs="*", help="Specific services to start (default: all)")
    p_up.add_argument("--no-build", action="store_true", help="Skip image build")
    p_up.add_argument("--no-migrate", action="store_true", help="Skip auto migration")
    p_up.add_argument("--pgadmin", action="store_true", help="Also start pgAdmin")

    # down
    p_down = sub.add_parser("down", help="Stop and remove containers")
    p_down.add_argument("services", nargs="*", help="Specific services to stop (default: all)")

    # restart
    p_restart = sub.add_parser("restart", help="Restart services")
    p_restart.add_argument("services", nargs="*")

    # logs
    p_logs = sub.add_parser("logs", help="View service logs")
    p_logs.add_argument("services", nargs="*")
    p_logs.add_argument("-f", "--follow", action="store_true")
    p_logs.add_argument("--tail", type=int, default=100, metavar="N")

    # status
    sub.add_parser("status", help="Show pod and container status")

    # build
    p_build = sub.add_parser("build", help="Build container images")
    p_build.add_argument("services", nargs="*")

    # migrate
    sub.add_parser("migrate", help="Run Alembic DB migrations")

    # shell
    p_shell = sub.add_parser("shell", help="Open bash in a container")
    p_shell.add_argument("service", nargs="?", default="backend")

    # psql
    sub.add_parser("psql", help="Open psql in the postgres container")

    # health
    sub.add_parser("health", help="Check service health endpoints")

    # seed
    sub.add_parser("seed", help="Seed demo users (admin@kyc.com, user@kyc.com)")

    # clean
    p_clean = sub.add_parser("clean", help="Remove all containers and volumes")
    p_clean.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    return p


COMMAND_MAP = {
    "up":      cmd_up,
    "down":    cmd_down,
    "restart": cmd_restart,
    "logs":    cmd_logs,
    "status":  cmd_status,
    "build":   cmd_build,
    "migrate": cmd_migrate,
    "shell":   cmd_shell,
    "psql":    cmd_psql,
    "health":  cmd_health,
    "seed":    cmd_seed,
    "clean":   cmd_clean,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not shutil.which("podman"):
        err("'podman' not found in PATH. Install Podman: https://podman.io/getting-started/installation")
        sys.exit(1)

    fn = COMMAND_MAP.get(args.command)
    if fn:
        try:
            fn(args)
        except KeyboardInterrupt:
            print()
            warn("Interrupted.")
            sys.exit(0)
        except subprocess.CalledProcessError as exc:
            err(f"Command failed (exit {exc.returncode}): {exc.cmd}")
            sys.exit(exc.returncode)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
