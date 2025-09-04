# 📌 GitHub Issues Plan — Django Boilerplate (API-only)

We keep code in `/apps/` for clear modular separation.  
Core principles: async emails via Celery, Django Groups for RBAC, feature flags via `django-waffle`, pre-commit enforced linting, no React/Next.js here.

---

## Phase 0 — Bootstrap & DX

### Issue 1 — Project scaffold
- Create structure:
/apps/
accounts/ # custom user, auth endpoints, groups
api/ # DRF routers, schema, example viewsets
core/ # utils, mixins, validators, enums, pagination
emails/ # EmailTemplate model, async send
featureflags/ # waffle wrapper, helpers
files/ # optional S3/MinIO signed uploads
ops/ # healthz, readyz, version, backups
config/ # settings/, asgi.py, wsgi.py, celery.py
settings/
base.py
local.py
test.py
prod.py
/compose/ # docker-compose files
/docs/ # mkdocs-ready docs
/scripts/ # smoke, backup, release helpers
Makefile
pyproject.toml
pytest.ini
.pre-commit-config.yaml
- Add Make targets: `dev-up`, `dev-down`, `migrate`, `seed`, `api-shell`, `test`, `lint`, `format`, `backup`.
- Add `.editorconfig`, `.gitignore`, PR templates.

---

### Issue 2 — Docker & Compose
- Services: `api`, `postgres`, `redis`, `mailpit`, `minio`, `celery`, `celery-beat`.
- Optional RabbitMQ via `RABBITMQ_ENABLED=true`.
- Healthchecks for db/cache.

---

### Issue 3 — Settings (`django-environ`)
- Split: base/local/test/prod.
- Validate required env vars; fail clearly if missing.
- JSON logging in prod, console pretty in dev.
- Static/media storage: S3/MinIO.

---

### Issue 4 — CI (GitHub Actions)
- Jobs: `pre-commit`, `pytest`, `docker-build`.
- Coverage gate ≥ 80%.
- Cache pip.

---

## Phase 1 — Auth, Groups, Feature Flags, Emails

### Issue 5 — Custom User & Auth
- Custom User (email login, `name`, `avatar`, `is_active`, `last_seen`).
- `django-allauth` for email+password; verification required.
- DRF endpoints: register, login, logout, password reset.
- Throttling for auth endpoints.

---

### Issue 6 — Groups RBAC
- Seed groups: `Admin`, `Manager`, `Member`, `ReadOnly`.
- Command `sync_groups` to ensure roles/permissions.
- DRF permission class `HasGroup`.

---

### Issue 7 — Feature Flags
- Install `django-waffle`.
- Helpers: `flags.is_enabled("EMAIL_EDITOR")`.
- Default flags: `FILES`, `EMAIL_EDITOR`, `RABBITMQ`.
- Guard DRF routes by flag.

---

### Issue 8 — Email Templates
- Model `EmailTemplate { key, subject, html, text, updated_by }`.
- Loader w/ cache; fallback to filesystem defaults.
- Preview endpoint in dev.
- Editable in admin.

---

### Issue 9 — Async Emails (Celery)
- Service `emails.services.send_email(key, to, ctx)`.
- Task `emails.tasks.send_email_task`.
- Mailpit in dev, SMTP in prod.
- `EmailMessageLog` tracks status/error.

---

## Phase 2 — Async, DRF API, Tests

### Issue 10 — Celery Baseline
- Config in `/apps/config/celery.py`.
- Broker = Redis, switch to RabbitMQ if enabled.
- Celery Beat for periodic jobs (cleanup, backups).

---

### Issue 11 — DRF API shell
- Versioned `/api/v1/`.
- `drf-spectacular` schema at `/schema/`.
- Swagger + Redoc.
- Example resource (`notes`).

---

### Issue 12 — Testing Framework
- Pytest + pytest-django + factory_boy.
- Fixtures: `user`, `auth_client`, `celery_eager`, `mailpit`.
- Coverage ≥ 80%, mypy strict.

---

### Issue 13 — Files & Media (Optional, Flagged)
- Storage: S3/MinIO.
- Signed upload/download endpoints.
- Validate size/type.

---

## Phase 3 — Security & Ops

### Issue 14 — Security headers
- Middleware for HSTS, CSP, Referrer-Policy, Permissions-Policy.
- Secure cookies.
- Admin at `/admin`; optional IP allowlist.

---

### Issue 15 — Rate limiting
- DRF throttles backed by Redis.
- Strict login throttle.
- Denylist/allowlist via env.

---

### Issue 16 — Observability
- Sentry DSN env.
- OpenTelemetry exporter (OTLP).
- Optional Prometheus metrics endpoint.

---

### Issue 17 — Backups
- `scripts/backup_db.sh` → S3/MinIO.
- Celery Beat nightly backup.
- Retention cleanup.

---

## Phase 4 — DX & Docs

### Issue 18 — Seed Data
- `manage.py seed_demo` adds sample user + templates.
- `DEMO_MODE=true` shows banner.

---

### Issue 19 — Docs & README
- `/docs/` with quick start, env vars, flags, emails, Celery, testing.
- Polished `README.md`.

---

## Cross-cutting

### Issue 20 — Pre-commit as source of truth
- `.pre-commit-config.yaml`: `ruff`, `black`, `isort`, `mypy`, `bandit`, `pip-audit`.
- `make lint` = `pre-commit run --all-files`.

---

# 📘 README.md

## Django Boilerplate (API-only)

Production-ready Django starter with:
- **Apps in `/apps/`**
- Async emails via Celery (Redis default, RabbitMQ optional)
- Feature flags (`django-waffle`)
- Group-based permissions
- Editable email templates (HTML in DB)
- Pre-commit for lint/type checks
- Healthchecks, backups, observability

---

### 🚀 Quick start

```bash
cp .env.example .env
make dev-up
make migrate
make seed
curl http://localhost:8000/healthz

📂 Project layout
/apps/
  accounts/      # User model, auth, Groups
  api/           # DRF routers, schema
  core/          # utilities
  emails/        # EmailTemplate + Celery send
  featureflags/  # Waffle wrappers
  files/         # S3/MinIO storage (optional)
  ops/           # healthz, backups
  config/        # settings, asgi, wsgi, celery
/compose/        # docker-compose
/scripts/        # helpers
/docs/           # dev docs

⚙️ Environment
DJANGO_SECRET_KEY=...
DATABASE_URL=postgres://...
REDIS_URL=redis://...
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=Boilerplate <noreply@example.com>
ALLOWED_HOSTS=localhost,127.0.0.1

RABBITMQ_ENABLED=false
SENTRY_DSN=...
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

🛠️ Commands
make dev-up / make dev-down → start/stop full stack

make migrate → run migrations

make seed → demo user & sample data

make test → pytest + coverage

make lint / make format → pre-commit hooks

make backup → run DB backup

🔐 Auth & Permissions

Custom User (email login)

Groups: Admin, Manager, Member, ReadOnly

Guard endpoints with DRF permission classes

✉️ Emails

Editable DB templates (EmailTemplate)

All sends go through Celery tasks

Mailpit at http://localhost:8025 in dev

Preview in dev: /dev/emails/preview/<key>

🚦 Feature Flags

Backed by django-waffle

Default: FILES, EMAIL_EDITOR, RABBITMQ

Guard API endpoints and background tasks

🔍 Observability

Sentry for errors

OTEL exporter optional

/healthz (alive), /readyz (db/cache/migrations), /version

🛡️ Security

Secure headers, cookies

DRF throttles (Redis)

Admin optional IP allowlist

✅ Testing

Pytest + factory_boy

Fixtures: user, auth_client, celery_eager

Coverage ≥ 80%

mypy strict on /apps

💾 Backups

Nightly Celery beat job

scripts/backup_db.sh → S3/MinIO

Retention cleanup

