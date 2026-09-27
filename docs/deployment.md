# Deployment

The whole system is one `docker compose` stack, so a single small VPS is enough
for a few dozen companies. Nothing here needs Kubernetes.

## What runs

| Service | Image | Notes |
|---|---|---|
| `db` | postgres:16-alpine | the only stateful service worth backing up |
| `redis` | redis:7-alpine | cache + Celery broker; losing it costs nothing permanent |
| `backend` | built from `backend/` | Django, served by gunicorn in production |
| `worker` | same image | Celery worker (payroll calculation, report generation) |
| `beat` | same image | Celery Beat — the 08:00 Africa/Cairo monthly-report job |
| `frontend` | built from `frontend/` | Next.js |

## Single VPS (recommended)

A 2 vCPU / 4 GB machine is comfortable. **Password hashing is deliberately
expensive**, so CPU matters more than RAM at sign-in time: on a loaded 4-core
box, Argon2id at the tuned parameters in `core/hashers.py` takes ~1s. If sign-in
feels slow, that is the machine, not the code — give it more CPU before
weakening the hash.

```bash
git clone <your-repo> hrms && cd hrms
cp .env.example .env
```

Then edit `.env`:

```ini
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<50+ random characters>
DJANGO_ALLOWED_HOSTS=hr.example.com
FRONTEND_ORIGIN=https://hr.example.com
CORS_ALLOWED_ORIGINS=https://hr.example.com
CSRF_TRUSTED_ORIGINS=https://hr.example.com
AUTH_COOKIE_SECURE=True

POSTGRES_PASSWORD=<a real password>
DATABASE_URL=postgres://hrms:<that password>@db:5432/hrms

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_HOST_USER=<smtp user>
EMAIL_HOST_PASSWORD=<smtp key>
DEFAULT_FROM_EMAIL=payroll@example.com

NEXT_PUBLIC_API_URL=https://hr.example.com
```

```bash
make build && make up && make migrate
docker compose run --rm backend python manage.py createsuperuser
```

### Production process

`backend`'s default command is Django's development server, which is fine for
local work and wrong for production. Override it in a compose override file:

```yaml
# docker-compose.prod.yml
services:
  backend:
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120
  frontend:
    command: npm run start
```

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### TLS and routing

Put Caddy or nginx in front and terminate TLS there. Caddy is two lines:

```
hr.example.com {
  handle_path /api/* { reverse_proxy backend:8000 }
  handle_path /admin/* { reverse_proxy backend:8000 }
  handle_path /media/* { reverse_proxy backend:8000 }
  handle { reverse_proxy frontend:3000 }
}
```

The auth cookies are `SameSite=Lax`, so serving the API and the app from the
**same origin** (as above) is the simplest correct setup. If you split them
across domains you must switch to `SameSite=None; Secure`, which needs HTTPS on
both.

### A note on the frontend container

In development the `frontend` service bind-mounts your working tree, keeps the
image's musl `node_modules` in a volume, builds into `.next-docker`, and runs as
the image's `node` user (uid 1000). In production none of that applies — build
the image and run `npm run start`; there is no bind mount.

### Static and media files

`backend/media/` holds generated reports and company logos — it is a named
volume (`backend-media`) and belongs in your backup. Run
`python manage.py collectstatic` if you serve the Django admin's assets through
your reverse proxy rather than WhiteNoise.

## Railway / Render / Fly

The same images work on any host that runs containers:

1. Provision managed Postgres and Redis; copy their URLs into `DATABASE_URL`
   and `REDIS_URL`/`CELERY_BROKER_URL`.
2. Deploy `backend/` as a web service with the gunicorn command above.
3. Deploy the **same image** twice more, as `celery -A config worker -l info`
   and `celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler`.
4. Deploy `frontend/` as a web service (`npm run build` then `npm run start`).
5. Media needs object storage on these platforms — their disks are ephemeral.
   Add `django-storages[s3]` and point `DEFAULT_FILE_STORAGE` at a bucket.

## Backups

```bash
docker compose exec db pg_dump -U hrms hrms | gzip > hrms-$(date +%F).sql.gz
docker run --rm -v hrms_backend-media:/m -v "$PWD":/b alpine \
  tar czf /b/media-$(date +%F).tar.gz -C /m .
```

Restore with `gunzip -c … | docker compose exec -T db psql -U hrms hrms`.

A closed payroll month is immutable in the application, but it is still just
rows in Postgres — the database backup is what actually protects it.

## Upgrades

```bash
git pull
make build
docker compose up -d
make migrate
```

Migrations are additive; check `git log` for any that rewrite payroll rows before
running them on production data.

## Health checks

| Endpoint | Meaning |
|---|---|
| `GET /api/v1/health/` | the process is alive (no dependencies touched) |
| `GET /api/v1/health/ready/` | PostgreSQL **and** Redis both answer |

Point your load balancer at `/api/v1/health/ready/` and your uptime monitor at
`/api/v1/health/`.

## The scheduled report

Beat fires `reports.send_scheduled_reports` every day at 08:00 Africa/Cairo. For
each active company whose `report_day` is today it sends the **previous** month's
workbook if that month is closed, and a reminder to close it if not. Both paths
are covered by tests in `backend/reports/tests/test_delivery.py`.

Verify it is scheduled:

```bash
docker compose exec backend python manage.py shell -c \
  "from django_celery_beat.models import PeriodicTask; print(list(PeriodicTask.objects.values_list('name', flat=True)))"
```
