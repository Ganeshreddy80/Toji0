# ============================================================================
# Toji — Makefile
# Build automation and development commands
# ============================================================================
# Usage:
#   make help       Show all available commands
#   make install    Install dependencies
#   make lint       Run all linters
#   make test       Run test suite
#   make check      Run all checks (lint + typecheck + test)
# ============================================================================

.PHONY: help install install-dev lint format typecheck test test-cov test-unit test-integration check clean docker-up docker-down docker-logs

# Default target
.DEFAULT_GOAL := help

# ── Variables ──────────────────────────────────────────────────────────────
PYTHON := python3
PIP := pip
PYTEST := pytest
RUFF := ruff
MYPY := mypy
BLACK := black

# ── Help ───────────────────────────────────────────────────────────────────
help: ## Show this help message
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║                    Toji — Build Commands                    ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ── Installation ───────────────────────────────────────────────────────────
install: ## Install production dependencies
	$(PIP) install -r requirements.txt

install-dev: ## Install development dependencies
	$(PIP) install -e ".[dev]"
	pre-commit install

# ── Linting ────────────────────────────────────────────────────────────────
lint: ## Run ruff linter
	$(RUFF) check .

lint-fix: ## Run ruff linter with auto-fix
	$(RUFF) check --fix .

# ── Formatting ─────────────────────────────────────────────────────────────
format: ## Format code with ruff
	$(RUFF) format .

format-check: ## Check formatting without changes
	$(RUFF) format --check .

# ── Type Checking ──────────────────────────────────────────────────────────
typecheck: ## Run mypy type checker
	$(MYPY) backend agents analytics memory mcp workflows

# ── Testing ────────────────────────────────────────────────────────────────
test: ## Run all tests
	$(PYTEST) tests/

test-unit: ## Run unit tests only
	$(PYTEST) tests/unit/

test-integration: ## Run integration tests only
	$(PYTEST) tests/integration/ -m integration

test-cov: ## Run tests with coverage report
	$(PYTEST) tests/ --cov --cov-report=html --cov-report=term-missing

test-fast: ## Run tests excluding slow tests
	$(PYTEST) tests/ -m "not slow"

# ── Combined Checks ───────────────────────────────────────────────────────
check: lint format-check typecheck test ## Run all checks (lint + format + typecheck + test)

ci: lint format-check typecheck test-cov ## Run CI pipeline checks

# ── Docker ─────────────────────────────────────────────────────────────────
docker-up: ## Start Docker services
	docker-compose up -d

docker-down: ## Stop Docker services
	docker-compose down

docker-logs: ## Follow Docker service logs
	docker-compose logs -f

docker-rebuild: ## Rebuild and restart Docker services
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d

# ── Database ───────────────────────────────────────────────────────────────
db-migrate: ## Run database migrations
	alembic upgrade head

db-rollback: ## Rollback last database migration
	alembic downgrade -1

db-create-migration: ## Create new migration (usage: make db-create-migration MSG="description")
	alembic revision --autogenerate -m "$(MSG)"

# ── Cleanup ────────────────────────────────────────────────────────────────
clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf dist/ build/

# ── Development ────────────────────────────────────────────────────────────
dev: ## Start development server
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

shell: ## Open Python shell with project context
	$(PYTHON) -i -c "print('Toji Development Shell')"
