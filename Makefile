# Lupus Ex Machina — single entry point for every development command.
#
# The same targets are used locally and in the container build, so there is only
# one way to run the test suite, the linters and the application.

BACKEND      := backend
FRONTEND     := frontend
# --directory makes uv treat backend/ as the working directory, so pytest, ruff
# and mypy all resolve backend/pyproject.toml as their configuration file.
UV           := uv --directory $(BACKEND)
NPM          := npm --prefix $(FRONTEND)
IMAGE        := lupus-ex-machina
CONTAINER    := lupus-ex-machina-check

# Defaults of the `play` target, overridable: make play SEED=7 PLAYERS=6
SEED         ?= 1
PLAYERS      ?= 8

.DEFAULT_GOAL := help
.PHONY: help install test test-backend lint lint-backend lint-frontend format \
        typecheck run run-frontend play build build-frontend build-image check-image clean

help: ## List the available targets
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install backend and frontend dependencies
	$(UV) sync
	$(NPM) install

# --- Tests -------------------------------------------------------------------

test: test-backend ## Run the whole test suite

test-backend: ## Run the backend test suite with coverage
	$(UV) run pytest

# --- Quality -----------------------------------------------------------------

lint: lint-backend lint-frontend ## Lint and type-check everything

lint-backend: ## Lint, check formatting and type-check the backend
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy

lint-frontend: ## Lint, check formatting and type-check the frontend
	$(NPM) run lint
	$(NPM) run format:check
	$(NPM) run typecheck

format: ## Apply the formatters
	$(UV) run ruff format .
	$(UV) run ruff check --fix .
	$(NPM) run format

typecheck: ## Type-check the backend only
	$(UV) run mypy

# --- Run ---------------------------------------------------------------------

run: ## Serve the API and the built frontend on APP_PORT (default 8000)
	$(UV) run lupus-ex-machina

run-frontend: ## Start the Vite dev server with hot reload
	$(NPM) run dev

play: ## Play one game in the console with scripted agents (SEED=1 PLAYERS=8)
	$(UV) run lupus-play --seed $(SEED) --players $(PLAYERS)

# --- Build -------------------------------------------------------------------

build: build-frontend ## Build every deployable artefact

build-frontend: ## Build the frontend into frontend/dist
	$(NPM) run build

build-image: ## Build the production Docker image
	docker build -t $(IMAGE) .

check-image: ## Build the image, start it and probe /health
	./scripts/check-image.sh $(IMAGE) $(CONTAINER)

# --- Housekeeping ------------------------------------------------------------

clean: ## Remove build outputs and tool caches
	rm -rf $(FRONTEND)/dist $(BACKEND)/.pytest_cache $(BACKEND)/.ruff_cache \
	       $(BACKEND)/.mypy_cache $(BACKEND)/.coverage $(BACKEND)/coverage.xml
	find $(BACKEND) -type d -name __pycache__ -prune -exec rm -rf {} +
