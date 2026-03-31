# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for KYC Platform desktop application.

Bundles:
  - kyc_launcher.py (entry point / launcher)
  - FastAPI backend (app package + main.py)
  - Built React frontend (frontend/dist/)
  - All required hidden imports for SQLAlchemy, uvicorn, LangGraph, etc.

Build command:
    pyinstaller kyc.spec

Output: dist/KYCPlatform/KYCPlatform.exe (Windows)
        dist/KYCPlatform/KYCPlatform       (Linux/macOS)
"""

import os
import sys
from pathlib import Path

block_cipher = None

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Spec file lives at desktop/pyinstaller/; project root is two levels up
SPEC_DIR = Path(SPECPATH)              # noqa: F821  (PyInstaller built-in)
PROJECT_ROOT = SPEC_DIR.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

# ---------------------------------------------------------------------------
# Data files to bundle
# ---------------------------------------------------------------------------

datas = []

# Include the entire backend source tree
datas.append((str(BACKEND_DIR), "backend"))

# Include the built React frontend (served by FastAPI as static files)
if FRONTEND_DIST.exists():
    datas.append((str(FRONTEND_DIST), "frontend/dist"))

# Include alembic migrations
alembic_dir = BACKEND_DIR / "alembic"
if alembic_dir.exists():
    datas.append((str(alembic_dir), "backend/alembic"))

# Include alembic.ini
alembic_ini = BACKEND_DIR / "alembic.ini"
if alembic_ini.exists():
    datas.append((str(alembic_ini), "backend"))

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

a = Analysis(
    scripts=[str(SPEC_DIR / "kyc_launcher.py")],
    pathex=[
        str(PROJECT_ROOT),
        str(BACKEND_DIR),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # --- FastAPI / Starlette ---
        "fastapi",
        "fastapi.middleware.cors",
        "fastapi.middleware.gzip",
        "fastapi.middleware.trustedhost",
        "fastapi.security",
        "starlette",
        "starlette.middleware",
        "starlette.middleware.base",

        # --- Uvicorn ---
        "uvicorn",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.logging",

        # --- SQLAlchemy / asyncpg / aiosqlite ---
        "sqlalchemy",
        "sqlalchemy.ext.asyncio",
        "sqlalchemy.dialects.postgresql",
        "sqlalchemy.dialects.sqlite",
        "asyncpg",
        "aiosqlite",

        # --- Pydantic / pydantic-settings ---
        "pydantic",
        "pydantic_settings",
        "pydantic.v1",

        # --- JWT / security ---
        "jose",
        "jose.jwt",
        "passlib",
        "passlib.context",
        "passlib.handlers.bcrypt",

        # --- Redis ---
        "redis",
        "redis.asyncio",

        # --- Celery ---
        "celery",
        "celery.app",
        "celery.app.task",

        # --- LangGraph / LangChain ---
        "langgraph",
        "langgraph.graph",
        "langchain_core",

        # --- OCR ---
        "easyocr",
        "cv2",
        "PIL",
        "PIL.Image",
        "numpy",

        # --- Fraud detection ---
        "rapidfuzz",
        "rapidfuzz.fuzz",

        # --- Alembic ---
        "alembic",
        "alembic.config",
        "alembic.command",

        # --- Stdlib extras ---
        "email.mime.text",
        "email.mime.multipart",
        "logging.handlers",

        # --- App modules ---
        "app",
        "app.core",
        "app.core.config",
        "app.core.database",
        "app.core.security",
        "app.core.redis_client",
        "app.core.logging_config",
        "app.models",
        "app.models.user",
        "app.models.kyc",
        "app.models.document",
        "app.models.audit_log",
        "app.schemas",
        "app.schemas.auth",
        "app.schemas.kyc",
        "app.schemas.user",
        "app.schemas.document",
        "app.repositories",
        "app.services",
        "app.services.auth_service",
        "app.services.kyc_service",
        "app.services.document_service",
        "app.agents",
        "app.agents.state",
        "app.agents.ingestion_agent",
        "app.agents.document_processing_agent",
        "app.agents.verification_agent",
        "app.agents.decision_agent",
        "app.agents.error_handler",
        "app.graph",
        "app.graph.kyc_graph",
        "app.api",
        "app.api.v1",
        "app.api.v1.router",
        "app.api.v1.endpoints.auth",
        "app.api.v1.endpoints.kyc",
        "app.api.v1.endpoints.documents",
        "app.api.v1.endpoints.admin",
        "app.tasks",
        "app.tasks.celery_app",
        "app.tasks.kyc_tasks",
        "app.utils",
        "app.utils.fraud_detection",
        "app.utils.ocr_utils",
        "app.utils.file_utils",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "pandas",
        "jupyter",
        "IPython",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ---------------------------------------------------------------------------
# PYZ archive
# ---------------------------------------------------------------------------

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # noqa: F821

# ---------------------------------------------------------------------------
# EXE
# ---------------------------------------------------------------------------

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KYCPlatform",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # Set True for debugging; False for production (no terminal)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(SPEC_DIR / "assets" / "icon.ico") if (SPEC_DIR / "assets" / "icon.ico").exists() else None,
)

# ---------------------------------------------------------------------------
# COLLECT (one-folder distribution)
# ---------------------------------------------------------------------------

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="KYCPlatform",
)
