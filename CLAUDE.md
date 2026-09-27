# CLAUDE.md — HR_management_system

Guidance for future Claude Code sessions in this repo. Read this first.

## What this is

A multi-tenant HR & payroll SaaS for Egyptian companies. The platform owner opens
accounts for **companies**; each company has **branches** and **employees**. Company
users enter attendance data **daily**; at month end the system calculates payroll
**exactly like `docs/reference/accounting_monthly.xlsx`**, locks the month, and emails
a monthly Excel report laid out like that workbook.

## Hard rules

1. **Never run `git commit`, `git push`, `git reset`, `git rebase`, or create branches.**
   The user drives git manually. Finish a phase, print changed files plus a suggested
   commit message, then stop.
2. **Work phase by phase** (see *Build phases*). End each phase with all tests and
   linters green, then stop and report. Do not start the next phase unasked.
3. **Money is `Decimal`, never `float`** — in Python and in JSON (send money as
   strings). On the client, `decimal.js` for any display math.
4. `docs/reference/accounting_monthly.xlsx` is the **source of truth**. Before changing
   payroll logic, re-read it with openpyxl (formula pass *and* `data_only=True` pass)
   and keep `backend/payroll/tests/test_workbook_parity.py` passing.
5. Keep it simple: shared-schema multi-tenancy, no microservices, no GraphQL.

## Layout

```
backend/          Django 5 + DRF. One app per bounded context.
  config/         settings.py (env-driven), urls, celery, wsgi/asgi
  core/           TenantModel/TenantManager, cookie JWT auth, permissions,
                  tenant middleware, base viewsets, health probes, hashers
  accounts/       User (email login), Membership, Invitation + auth endpoints
  companies/      Company, Branch, PayrollPolicy + platform & settings endpoints
  employees/      Employee, SalaryHistory + the Excel import wizard
  attendance/     DailyRecord + the grid's bulk upsert
  payroll/        Period, MonthlyAdjustment, Loan, PayrollLine
    services/     engine.py (pure Decimal math), aggregate.py (daily -> monthly),
                  runner.py (calculate/close/reopen), workbook.py, cache.py
  reports/        ReportFile; services/excel.py (live formulas), pdf.py,
                  mailer.py, layout.py, formula_eval.py
  audit/          AuditLog
frontend/         Next.js 15 App Router, TypeScript, Tailwind, shadcn/ui
  src/app/[locale]/(auth)/   login, accept-invite, forgot/reset password
  src/app/[locale]/(app)/    dashboard, daily-entry, employees, adjustments,
                             loans, payroll/[year]/[month], reports, settings,
                             platform
  src/components/shell/      app shell, sidebar, company switcher, user menu
  src/hooks/use-api.ts       one typed hook per resource, keyed by company
  src/i18n/                  next-intl routing / navigation / request config
  messages/                  ar.json + en.json — every visible string lives here
  scripts/check-rtl.mjs      fails the build on physical Tailwind utilities
  e2e/                       Playwright specs driving the real stack
docs/reference/   the source-of-truth workbook + its reverse-engineered spec
docs/deployment.md  single-VPS and PaaS deployment notes
```

## Commands

Everything runs through docker compose; the host only needs docker.

```bash
cp .env.example .env
make up          # dev: Django runserver + next dev (compiles on demand)
make up-prod     # gunicorn + a compiled frontend — what to use when not editing
make migrate
make seed        # demo company seeded from the reference workbook
make test        # backend pytest + frontend typecheck
make e2e         # Playwright, driving the real stack in a browser
make lint        # ruff, black, eslint, prettier, rtl-check
make fmt         # auto-fix formatting on both sides
make help        # every target
```

Demo sign-ins created by `make seed` (password `DemoPass!2026`):
`owner@hrms.test` (platform), `admin@demo.test` (company admin),
`entry@demo.test` (branch data entry).

Published host ports are shifted in `.env.example` (`5440/6390/8010/3000`) so the
stack starts on machines that already run postgres/redis/a dev server. Container
traffic always uses the standard ports.

Useful URLs: frontend `http://localhost:3000/ar`, API docs `http://localhost:8010/api/docs/`,
health `http://localhost:8010/api/v1/health/`.

## Conventions

**Backend**

- `ruff` + `black`, line length 100. `make fmt` before finishing a phase.
- Every tenant-owned model inherits `TenantModel` (company FK) and is read through a
  manager that requires an explicit `.for_company(company)`. Viewsets scope by
  `request.company`, set by middleware from the `X-Company-Id` header after the
  membership check. **Every endpoint needs a tenant-isolation test** proving a user of
  company A gets 404 on company B's objects.
- Payroll math lives in `payroll/services/engine.py` as pure functions with **no Django
  imports**: `calculate_line(inputs, policy) -> LineResult`, `getcontext().prec = 28`.
  Store computed values at 6 dp; round to 2 dp (`ROUND_HALF_UP`) only for display and
  in the report's `#,##0.00` number format.
- Closed periods are immutable: any write to their records returns 409.
- API validation errors are localized with `gettext`; `LocaleMiddleware` reads
  `Accept-Language`.

**Frontend**

- **Only logical Tailwind utilities**: `ms-/me-/ps-/pe-/start-/end-/text-start`. Never
  `ml-/mr-/pl-/pr-/left-/right-/text-left/text-right`. Flip directional icons with
  `rtl:rotate-180`. `npm run lint:rtl` (and an eslint rule) enforce this.
- `<html lang>` and `dir` come from the locale; `ar` is the default locale and RTL.
- Every visible string goes through `next-intl` — including zod error messages.
- Numbers use `Intl.NumberFormat(locale, { minimumFractionDigits: 2 })`; money columns
  carry the `.numeric` class so digits stay LTR and tabular inside Arabic pages.
- AG Grid gets `enableRtl` when the locale is `ar`.
- **Nothing is statically generated.** Every page belongs to a signed-in user of a
  specific company, so the `[locale]` layout deliberately has no
  `generateStaticParams` and pages render per request.

## The workbook

`docs/reference/workbook-spec.md` holds the verified column/formula table, the quirks
that must be preserved (30-day month basis, 1x overtime, fingerprint penalty computed
off earned days `H` not base salary `F`, insurance 11% with no income tax), and the
golden totals the parity test asserts. Read it before touching payroll.

## Build phases

Phases 1-6 are **complete**. 151 backend tests and 27 Playwright browser tests pass.

1. **Skeleton** — compose, Django + apps, Next.js with next-intl/fonts/shadcn, Makefile,
   linters, health endpoint. *(done)*
2. **Payroll core** — models, policy, engine, aggregation, workbook parity test,
   tenant manager + isolation tests, `seed_demo`. *(done)*
3. **API + auth** — 50+ endpoints, roles, invitations, audit log, OpenAPI, Redis
   caching, Celery calculate task. *(done)*
4. **Frontend core** — auth, company switcher, employees + import, daily-entry grid,
   adjustments/loans, dashboard. *(done)*
5. **Monthly review + reports** — review grid, close/reopen, Excel generator (live
   formulas, RTL, payslip strips) with formula-level verification, PDF payslips,
   Beat email. *(done)*
6. **Platform admin + polish** — platform pages, settings, Playwright suite,
   deployment notes. *(done)*
7. *(on request)* ZKTeco fingerprint import; optional Egyptian income tax behind
   `income_tax_enabled`.

## Things worth knowing before you change them

- **Password hashing** is Argon2id at OWASP's recommended parameters
  (`core/hashers.py`), not Django's heavier default — the default cost several
  seconds per sign-in on a loaded box. Do not lower it further; add CPU instead.
- **The tenant guard is strict.** `Model.objects.all()` on a tenant-owned model
  *raises* `UnscopedTenantQueryError`. Use `.for_company(company)`, or
  `.all_objects` / `.unscoped()` where that is genuinely intended (seeders,
  platform-wide queries). Django's own traversal uses `all_objects` via
  `default_manager_name`, so related access keeps working.
- **The test suite uses its own Redis database (9)** and clears it between tests;
  sharing db 0 with the dev stack let login-throttle counters leak between tests.
- **Excel formulas are verified, not assumed.** `reports/services/formula_eval.py`
  parses the formulas back out of the generated file and evaluates them against
  the sheet's own inputs. Change a formula template and that test will tell you.
- **Nothing on the frontend is statically generated** — every page belongs to a
  signed-in user of a specific company.
- **The frontend container and your host share the working tree but not their
  build output.** The container is `node:alpine`, so its `node_modules` holds
  musl binaries and must stay in the `/app/node_modules` volume — the host's are
  glibc and will not load. It builds into `.next-docker` (`NEXT_DIST_DIR`) so a
  container dev server and a host `npm run build` cannot corrupt each other, and
  it runs as the image's `node` user (uid 1000) so nothing it writes into your
  checkout is root-owned.
- **Deleting a tenant needs `delete_company_data()`.** `Employee.branch` and
  `PayrollLine.employee` are `PROTECT` on purpose, so a plain `company.delete()`
  raises `ProtectedError`; the helper in `companies/services.py` walks the graph
  leaves-first. The platform API deliberately exposes **no DELETE** — companies
  are suspended, because payroll history must survive.
- **backend, worker and beat share one image** (`image: hrms-backend:latest` in
  the compose anchor). Without that shared name compose builds the same source
  three times, and rebuilding one leaves the others on stale code.
- **Both app containers run as uid 1000** (`app` in the backend image, `node` in
  the frontend one) so nothing they write into the bind-mounted working tree is
  root-owned.
- **`make up` compiles on demand and is slow to first paint.** `next dev` can
  take 30s+ to compile a route the first time it is opened, during which the
  sign-in button is disabled and shows a busy state. That is why
  `docker-compose.prod.yml` / `make up-prod` exists — use it unless you are
  editing the frontend.
- **Auth forms are `method="post"` and disable their submit button until
  hydrated.** Both guard the same bug: a click before React attaches used to
  trigger the browser's native GET submit, putting the password in the URL. The
  button shows a spinner and a "starting" label meanwhile, because a plain
  disabled button just looks broken.
- **`make e2e` serves its own production build on :3100**, so it never runs
  against the compose dev server (where Next compiles each route on first visit
  and a sign-in can exceed the timeout). That port is in `CORS_ALLOWED_ORIGINS`.
- **The access cookie lives 30 minutes, the refresh cookie 14 days, and
  `apiFetch` bridges the gap.** A 401 on a signed-in tab is the expected steady
  state, not an error: the client refreshes once (single-flight — `ROTATE_REFRESH_TOKENS`
  is on, so parallel refreshes would invalidate each other) and replays the
  request. Only a 401/403 *from the refresh itself* ends the session; a 429 from
  the auth throttle or a 5xx must not. When it does end, the client calls
  `/auth/logout` **before** redirecting: `middleware.ts` treats the mere presence
  of a cookie as signed-in and bounces you off `/login`, so redirecting with a
  dead cookie still set ping-pongs between the two pages. Without any of this the
  app silently empties after 30 minutes — signed-in shell, no company, every
  query disabled — which is exactly what `e2e/session.spec.ts` guards.
- **A platform admin usually belongs to no company.** `resolve_company` lets them
  through with a `None` membership, so `CompanyProvider` tops the session's
  memberships up with `/platform/companies/` for that role. Build a company list
  from `session.memberships` alone and the platform owner gets an app with no
  tenant selected and every query disabled.
