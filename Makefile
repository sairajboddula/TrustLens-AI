# =============================================================================
#  KYC Platform - Makefile
#
#  Usage:
#    make dev             Start full development stack (Docker)
#    make backend-dev     Start backend in hot-reload mode
#    make frontend-dev    Start Vite dev server
#    make test            Run all backend tests
#    make test-coverage   Run tests with HTML coverage report
#    make migrate         Apply database migrations
#    make migrate-new     Create a new migration (MSG=description)
#    make build-frontend  Build React frontend for production
#    make exe             Build Electron desktop installer
#    make exe-pyinstaller Build PyInstaller executable
#    make clean           Remove all build artefacts
#    make lint            Run code linters (flake8, isort check)
#    make format          Auto-format code (black, isort)
#    make help            Show this help
# =============================================================================

.PHONY: help dev stop backend-dev frontend-dev test test-coverage \
        migrate migrate-new build-frontend exe exe-pyinstaller \
        clean lint format install-backend install-frontend

# ---------------------------------------------------------------------------
# Default target
# ---------------------------------------------------------------------------

.DEFAULT_GOAL := help

help: ## Show available make targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'


# ---------------------------------------------------------------------------
# Docker Compose
# ---------------------------------------------------------------------------

dev: ## Start full development environment (Docker Compose)
	docker-compose up -d
	@echo ""
	@echo "Services started:"
	@echo "  Frontend:      http://localhost:3000"
	@echo "  Backend API:   http://localhost:8000"
	@echo "  Swagger Docs:  http://localhost:8000/docs"
	@echo "  Flower:        http://localhost:5555"

stop: ## Stop all Docker Compose services
	docker-compose down

logs: ## Tail logs for all services
	docker-compose logs -f

logs-backend: ## Tail backend logs only
	docker-compose logs -f backend


# ---------------------------------------------------------------------------
# Local development
# ---------------------------------------------------------------------------

backend-dev: ## Start FastAPI backend in hot-reload development mode
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000 --log-level debug

frontend-dev: ## Start Vite dev server on port 3000
	cd frontend && npm run dev

celery-dev: ## Start a Celery worker in development mode
	cd backend && celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2


# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

test: ## Run all backend tests with verbose output
	cd backend && pytest tests/ -v --asyncio-mode=auto

test-coverage: ## Run tests with HTML coverage report (opens htmlcov/index.html)
	cd backend && pytest tests/ -v \
	  --asyncio-mode=auto \
	  --cov=app \
	  --cov-report=html \
	  --cov-report=term-missing \
	  --cov-fail-under=70
	@echo ""
	@echo "Coverage report: backend/htmlcov/index.html"

test-fast: ## Run tests without slow integration tests
	cd backend && pytest tests/ -v --asyncio-mode=auto -m "not slow"

test-auth: ## Run authentication tests only
	cd backend && pytest tests/test_auth.py -v --asyncio-mode=auto

test-kyc: ## Run KYC endpoint tests only
	cd backend && pytest tests/test_kyc.py -v --asyncio-mode=auto

test-agents: ## Run agent tests only
	cd backend && pytest tests/test_agents.py -v --asyncio-mode=auto

test-fraud: ## Run fraud detection tests only
	cd backend && pytest tests/test_fraud_detection.py -v --asyncio-mode=auto


# ---------------------------------------------------------------------------
# Database migrations
# ---------------------------------------------------------------------------

migrate: ## Apply all pending Alembic migrations
	cd backend && alembic upgrade head

migrate-new: ## Create a new migration: make migrate-new MSG="add_column_foo"
ifndef MSG
	$(error MSG is required. Usage: make migrate-new MSG="description")
endif
	cd backend && alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Downgrade one migration step
	cd backend && alembic downgrade -1

migrate-history: ## Show migration history
	cd backend && alembic history --verbose

migrate-current: ## Show current migration revision
	cd backend && alembic current


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

install-backend: ## Install backend Python dependencies
	cd backend && pip install -r requirements.txt

install-frontend: ## Install frontend npm dependencies
	cd frontend && npm install

build-frontend: install-frontend ## Build the React frontend for production
	cd frontend && npm run build
	@echo "Frontend built: frontend/dist/"

build-docker: ## Build Docker images without starting them
	docker-compose build


# ---------------------------------------------------------------------------
# Desktop packaging
# ---------------------------------------------------------------------------

exe: build-frontend ## Build Electron desktop installer (Windows .exe / Linux AppImage)
	cd desktop/electron && npm install && npm run build
	@echo ""
	@echo "Electron installer: desktop/electron/dist/"

exe-pyinstaller: build-frontend ## Build PyInstaller .exe / binary
ifeq ($(OS),Windows_NT)
	cd desktop/pyinstaller && build_exe.bat
else
	cd desktop/pyinstaller && bash build_exe.sh
endif
	@echo ""
	@echo "PyInstaller binary: desktop/pyinstaller/dist/KYCPlatform/"


# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

lint: ## Run flake8 and isort --check
	cd backend && flake8 app/ tests/ --max-line-length=120 --exclude=__pycache__
	cd backend && isort app/ tests/ --check-only --diff

format: ## Auto-format code with black and isort
	cd backend && black app/ tests/ --line-length=120
	cd backend && isort app/ tests/

type-check: ## Run mypy type checking
	cd backend && mypy app/ --ignore-missing-imports


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

clean: ## Remove build artefacts, caches, and compiled files
	# Python
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -name "*.pyc" -delete 2>/dev/null || true
	rm -rf backend/.pytest_cache backend/htmlcov backend/.coverage
	# Frontend
	rm -rf frontend/dist frontend/node_modules/.vite
	# Desktop
	rm -rf desktop/electron/dist desktop/electron/node_modules
	rm -rf desktop/pyinstaller/build desktop/pyinstaller/dist
	@echo "Build artefacts removed."

clean-docker: ## Remove Docker containers, volumes, and images for this project
	docker-compose down -v --rmi local
