# HR_management_system — developer entry points.
# Everything runs through docker compose so the host only needs docker.

COMPOSE ?= docker compose
BE      := $(COMPOSE) run --rm backend
FE      := $(COMPOSE) run --rm frontend

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- lifecycle -------------------------------------------------------------
.PHONY: build up up-prod down restart logs ps
build:   ## Build all images
	$(COMPOSE) build
up:      ## Start the whole stack in the background (dev: compiles on demand)
	$(COMPOSE) up -d

up-prod: ## Start the stack with gunicorn and a compiled frontend (fast)
	$(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml up -d
down:    ## Stop the stack (keeps volumes)
	$(COMPOSE) down
restart: ## Restart the stack
	$(COMPOSE) down && $(COMPOSE) up -d
logs:    ## Tail logs of every service
	$(COMPOSE) logs -f --tail=100
ps:      ## Show service status
	$(COMPOSE) ps

# --- django ----------------------------------------------------------------
.PHONY: migrate makemigrations seed superuser shell dbshell
migrate:        ## Apply database migrations
	$(BE) python manage.py migrate
makemigrations: ## Create new migrations
	$(BE) python manage.py makemigrations
seed:           ## Load the demo company from the reference workbook
	$(BE) python manage.py seed_demo
superuser:      ## Create a platform admin interactively
	$(COMPOSE) run --rm backend python manage.py createsuperuser
shell:          ## Django shell
	$(COMPOSE) run --rm backend python manage.py shell
dbshell:        ## psql prompt
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-hrms} -d $${POSTGRES_DB:-hrms}

# --- translations ----------------------------------------------------------
.PHONY: messages compilemessages
messages:        ## Extract translatable strings (ar, en)
	$(BE) python manage.py makemessages -l ar -l en --ignore=.venv
compilemessages: ## Compile .po -> .mo
	$(BE) python manage.py compilemessages

# --- quality ---------------------------------------------------------------
.PHONY: test test-be test-fe lint lint-be lint-fe fmt rtl-check check
test: test-be test-fe ## Run every test suite (not e2e — see `make e2e`)

test-be: ## Backend: pytest
	$(BE) pytest

test-be-payroll: ## Backend: just the workbook parity + engine tests
	$(BE) pytest payroll -q

test-fe: ## Frontend: type-check
	$(FE) npm run typecheck

e2e: ## Playwright: drive the real stack in a browser (needs `make up` for the API)
	cd frontend && npx playwright test

e2e-ui: ## Playwright in headed mode, for watching it work
	cd frontend && npx playwright test --headed

e2e-install: ## One-off: download the browser Playwright drives
	cd frontend && npx playwright install --with-deps chromium

lint: lint-be lint-fe rtl-check ## Run every linter

lint-be: ## Backend: ruff + black --check
	$(BE) ruff check .
	$(BE) black --check .

lint-fe: ## Frontend: eslint + prettier --check
	$(FE) npm run lint
	$(FE) npm run format:check

rtl-check: ## Fail on physical (non-logical) Tailwind utilities
	$(FE) npm run lint:rtl

fmt: ## Auto-format backend and frontend
	$(BE) ruff check --fix .
	$(BE) black .
	$(FE) npm run format

check: lint test ## Lint then test — what CI runs

# --- reports ---------------------------------------------------------------
.PHONY: report
report: ## Generate the demo company's Excel report into backend/media
	$(BE) python manage.py shell -c "\
from payroll.models import Period; \
from reports.services.generator import generate_excel; \
p = Period.all_objects.order_by('-year','-month').first(); \
print(generate_excel(p).file.name)"
