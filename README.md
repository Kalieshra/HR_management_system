# HR_management_system

Multi-tenant HR & payroll SaaS for Egyptian companies. Companies record attendance
daily; at month end the system calculates payroll exactly like the reference Excel
workbook, locks the month, and emails a monthly report in the same layout.

Arabic (RTL) is the default interface language; English (LTR) is fully supported.

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, Django 5, DRF, SimpleJWT (HttpOnly cookies), drf-spectacular |
| Database | PostgreSQL 16 |
| Cache / broker | Redis 7 (`django-redis`, Celery broker + results) |
| Async | Celery 5 + Celery Beat |
| Documents | openpyxl (Excel), WeasyPrint (PDF payslips) |
| Frontend | Next.js 15 (App Router, TS), Tailwind, shadcn/ui, next-intl, TanStack Query, AG Grid |
| Infra | Docker Compose, Makefile |

## Setup

```bash
cp .env.example .env
make up-prod     # db, redis, backend, worker, beat, frontend — compiled, fast
make migrate
make seed        # demo company from the reference workbook
```

**Use `make up-prod` unless you are editing the code.** `make up` runs Django's
dev server and `next dev`, which compile each page the first time it is opened —
on a modest machine the first sign-in page can take half a minute to appear, and
the sign-in button stays busy until it does. `make up-prod` builds once at
start-up and then serves pages in ~0.1s.

`make seed` creates three sign-ins, all with the password `DemoPass!2026`:

| Email | Role |
|---|---|
| `owner@hrms.test` | platform admin — every company |
| `admin@demo.test` | company admin — الشركة التجريبية |
| `entry@demo.test` | branch data entry — one branch only |

The demo company is loaded straight from `accounting_monthly.xlsx`, so the
February 2026 payroll screen shows the workbook's numbers to the cent:
**162,500.00** salaries, **156,959.26** earnings, **42,220.37** deductions,
**114,738.89** net.

Then open:

| What | URL |
|---|---|
| App (Arabic) | http://localhost:3000/ar |
| App (English) | http://localhost:3000/en |
| API docs | http://localhost:8010/api/docs/ |
| Health | http://localhost:8010/api/v1/health/ |
| Readiness | http://localhost:8010/api/v1/health/ready/ |

### Ports

`.env.example` publishes the backend on **8010**, PostgreSQL on **5440** and Redis on
**6390**, so the stack starts on machines that already run those services locally.
Change `BACKEND_HOST_PORT` / `POSTGRES_HOST_PORT` / `REDIS_HOST_PORT` in `.env` if you
prefer the standard ports. Container-to-container traffic always uses 8000/5432/6379.

## Everyday commands

```bash
make help        # list every target
make test        # backend pytest + frontend typecheck
make lint        # ruff, black, eslint, prettier, rtl-check
make fmt         # auto-format both sides
make logs        # tail all services
make down        # stop (volumes kept)
```

## Working without Docker

```bash
# backend
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python manage.py check

# frontend
cd frontend && npm install && npm run dev
```

## Repository layout

```
backend/            Django project (config/) + one app per bounded context
frontend/           Next.js App Router application
docs/reference/     accounting_monthly.xlsx (source of truth) + workbook-spec.md
CLAUDE.md           architecture, conventions and build phases
```

## The reference workbook

`docs/reference/accounting_monthly.xlsx` defines payroll. Its columns, formulas,
quirks and golden totals are documented in `docs/reference/workbook-spec.md`, and
`backend/payroll/tests/test_workbook_parity.py` (phase 2) asserts the engine
reproduces every cached value in it. Payroll changes start by reading that spec.

## What it does

**Platform owner** opens company accounts and invites their admins.
**Company admins** manage branches, employees, users and the payroll policy, review
and close each month, and download or email the report. **Branch data-entry users**
record attendance for their own branches and nothing else.

| Screen | Purpose |
|---|---|
| `/dashboard` | month status, daily-entry completion per branch, totals, alerts |
| `/daily-entry` | the main screen — a keyboard-first grid, one row per employee, autosaving |
| `/employees` | master data, salary history, Excel import with a per-row preview |
| `/adjustments`, `/loans` | monthly amounts; loans charge one instalment per month |
| `/payroll/[year]/[month]` | the review grid, laid out exactly like the Excel columns A→AH |
| `/reports` | generated workbooks and payslips, with resend |
| `/settings` | branches, users and invitations, versioned payroll policy |
| `/platform` | every company on the installation |

## Testing

| Suite | What it covers |
|---|---|
| `make test-be-payroll` | **workbook parity** — every calculated column of all 23 employees, plus synthetic tests for the four columns the fixture leaves at zero |
| `make test-be` | 151 tests: engine, aggregation, period lifecycle, auth, tenant isolation on every endpoint, Excel formula verification, report delivery |
| `make e2e` | 27 Playwright tests driving a real browser: sign-in, RTL/LTR, the daily-entry grid, the review grid's totals, closing a month, generating a report |

Tenant isolation is asserted per endpoint: a user of company A gets a 404 — never a
403 — for every one of company B's objects.

## Deployment

See `docs/deployment.md` for a single-VPS setup (compose + Caddy) and notes for
Railway/Render/Fly, backups, and the scheduled monthly email.

## Status

Phases 1-6 are complete. Phase 7 (ZKTeco fingerprint import and optional Egyptian
income tax behind `income_tax_enabled`) is deliberately not built yet.
# HR_management_system
