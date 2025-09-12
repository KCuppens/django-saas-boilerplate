# Django SaaS Boilerplate

A production-ready Django SaaS boilerplate with async emails, feature flags, RBAC, and comprehensive API.

[![CI](https://github.com/yourusername/django-saas-boilerplate/workflows/CI/badge.svg)](https://github.com/yourusername/django-saas-boilerplate/actions)
[![Coverage](https://codecov.io/gh/yourusername/django-saas-boilerplate/branch/main/graph/badge.svg)](https://codecov.io/gh/yourusername/django-saas-boilerplate)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🚀 Features

- **🏗️ Modern Architecture**: Apps organized in `/apps/` for clear modular separation
- **📧 Async Emails**: Template-based emails via Celery with database storage
- **🏃‍♂️ Feature Flags**: `django-waffle` integration with management commands
- **👥 RBAC System**: Role-based access control with Django Groups
- **🔐 Authentication**: Custom user model with email login via `django-allauth`
- **🌐 REST API**: DRF with OpenAPI schema, Swagger UI, and versioning
- **🐳 Docker Ready**: Multi-service Docker Compose setup
- **🔍 Observability**: Sentry integration, health checks, and OpenTelemetry support
- **🛡️ Security**: Security headers, rate limiting, and pre-commit hooks
- **📦 Backups**: Automated database backups with retention policies
- **🧪 Testing**: Pytest with factory_boy and 80%+ coverage requirement

## 📂 Project Structure

```
/apps/
  accounts/      # User model, auth, Groups
  api/           # DRF routers, schema, example endpoints
  core/          # Utilities, mixins, permissions
  emails/        # EmailTemplate model + async sending
  featureflags/  # Waffle wrappers and helpers
  files/         # S3/MinIO storage (optional)
  ops/           # Health checks, backups, system tasks
  config/        # Settings, ASGI, WSGI, Celery config
/compose/        # Docker Compose configurations
/scripts/        # Backup and maintenance scripts
/docs/           # Documentation
```

## ⚡ Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL (if not using Docker)
- Redis (if not using Docker)

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/django-saas-boilerplate.git
cd django-saas-boilerplate

# Copy environment file
cp .env.example .env
# Edit .env with your settings
```

### 2. Using Docker (Recommended)

```bash
# Start all services
make dev-up

# Wait for services to be ready, then run migrations
make migrate

# Create groups and demo data
docker-compose exec api python manage.py sync_groups
docker-compose exec api python manage.py sync_flags
docker-compose exec api python manage.py seed_demo

# Visit the application
open http://localhost:8000/healthz
```

### 3. Local Development

```bash
# Install dependencies
make install

# Start supporting services only
docker-compose up -d postgres redis mailpit

# Run migrations
make migrate

# Create groups and demo data
python manage.py sync_groups
python manage.py sync_flags
python manage.py seed_demo

# Start development server
python manage.py runserver

# In another terminal, start Celery
celery -A apps.config worker -l info
```

## 🛠️ Available Commands

```bash
# Development
make dev-up          # Start all services with Docker
make dev-down        # Stop all services
make migrate         # Run database migrations
make seed            # Load demo data
make api-shell       # Open Django shell

# Code Quality
make lint            # Run pre-commit hooks
make format          # Format code with black/isort
make test            # Run tests with coverage
make check           # Run all checks (lint + test + type)

# Maintenance
make backup          # Create database backup
make clean           # Clean temporary files
```

## 🔧 Configuration

### Environment Variables

Key environment variables in `.env`:

```bash
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://django:django@localhost:5432/django_saas

# Redis & Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=localhost
EMAIL_PORT=1025
DEFAULT_FROM_EMAIL=Django SaaS <noreply@example.com>

# Optional: External Services
SENTRY_DSN=your-sentry-dsn
AWS_STORAGE_BUCKET_NAME=your-s3-bucket
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

### Feature Flags

Default feature flags (configurable via admin):

- `FILES`: Enable file upload functionality
- `EMAIL_EDITOR`: Enable email template editor
- `RABBITMQ`: Use RabbitMQ instead of Redis
- `ADVANCED_ANALYTICS`: Enable analytics features
- `BETA_FEATURES`: Enable beta features

## 👥 User Roles & Permissions

### Built-in Groups

- **Admin**: Full system access
- **Manager**: Management access with limited admin rights
- **Member**: Standard member access
- **ReadOnly**: Read-only access

### Demo Users (after running `seed_demo`)

- `admin@example.com` / `demo123` - Admin user
- `manager@example.com` / `demo123` - Manager user
- `member@example.com` / `demo123` - Member user
- `readonly@example.com` / `demo123` - ReadOnly user

## 📧 Email System

### Template-based Emails

Emails are stored as database templates with caching:

```python
from apps.emails.services import EmailService

# Send templated email
EmailService.send_email(
    template_key='welcome',
    to_email='user@example.com',
    context={'user_name': 'John Doe'},
    async_send=True  # Send via Celery
)
```

### Email Development

In development mode, emails are viewable at:

- Template list: `http://localhost:8000/dev/emails/`
- Preview: `http://localhost:8000/dev/emails/welcome/html/`
- Mailpit UI: `http://localhost:8025`

## 🌐 API Documentation

### Endpoints

- **Health**: `GET /healthz`, `/readyz`, `/livez`
- **API Schema**: `GET /schema/` (JSON), `/schema/swagger/` (UI)
- **Authentication**: `POST /api/v1/auth/users/register/`, `/auth/users/login/`
- **Notes API**: `GET/POST /api/v1/notes/` (example CRUD API)

### Authentication

The API uses session authentication by default. For API clients:

```bash
# Register new user
curl -X POST http://localhost:8000/api/v1/auth/users/register/ \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password1": "secretpass", "password2": "secretpass"}'

# Login and get session
curl -c cookies.txt -X POST http://localhost:8000/auth/login/ \
  -d "login=test@example.com&password=secretpass"

# Use authenticated endpoint
curl -b cookies.txt http://localhost:8000/api/v1/notes/
```

## 🐳 Docker Services

The Docker Compose setup includes:

- **api**: Django application server
- **postgres**: PostgreSQL database
- **redis**: Redis for caching and Celery
- **celery**: Celery worker for async tasks
- **celery-beat**: Celery scheduler for periodic tasks
- **mailpit**: Email testing server (http://localhost:8025)
- **minio**: S3-compatible object storage (optional)

### Production Deployment

For production, use the production compose file:

```bash
docker-compose -f compose/docker-compose.yml -f compose/docker-compose.prod.yml up -d
```

## 🔒 Security Features

- **Security Headers**: HSTS, CSP, X-Frame-Options via middleware
- **Rate Limiting**: DRF throttles backed by Redis
- **CSRF Protection**: Django CSRF with secure cookies
- **Input Validation**: Comprehensive serializer validation
- **SQL Injection Protection**: Django ORM with parameterized queries
- **XSS Protection**: Django template auto-escaping

## 📊 Monitoring & Observability

### Health Checks

- `/healthz` - Basic health check
- `/readyz` - Readiness check (database, cache, migrations)
- `/livez` - Liveness check for Kubernetes

### Metrics & Tracing

- **Sentry**: Error tracking and performance monitoring
- **OpenTelemetry**: Distributed tracing (optional)
- **System Metrics**: CPU, memory, disk usage for staff users

## 💾 Backup System

Automated PostgreSQL backups:

```bash
# Manual backup
./scripts/backup_db.sh

# Automated daily backups via Celery Beat
# Retention: 7 days (configurable)
# Location: /backups/ directory
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests with coverage
make test

# Run specific tests
pytest apps/accounts/tests/
pytest -k test_user_creation

# Run with different settings
DJANGO_SETTINGS_MODULE=apps.config.settings.test pytest
```

### Testing Features

- **pytest** with **pytest-django**
- **factory_boy** for test data generation
- **Coverage** requirement ≥ 80%
- **Fixtures**: `user`, `auth_client`, `celery_eager`
- **Integration tests** with Docker services

## 📝 Development Workflow

### Code Quality

The project uses pre-commit hooks for code quality:

```bash
# Install pre-commit hooks
make install

# Run manually
make lint

# Tools used:
# - ruff (linting)
# - black (formatting)
# - isort (import sorting)
# - mypy (type checking)
# - bandit (security)
```

### Adding New Features

1. Create feature in appropriate app under `/apps/`
2. Add tests with good coverage
3. Update API documentation if needed
4. Add feature flag if appropriate
5. Update README if it affects setup/usage

## 📚 Additional Resources

### Django Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Django Allauth](https://django-allauth.readthedocs.io/)

### Infrastructure

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)
- [Celery Documentation](https://docs.celeryproject.org/)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`make test`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Check the `/docs/` directory for detailed guides
- **Issues**: Open an issue on GitHub for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions and ideas

---

**Built with ❤️ using Django, DRF, Celery, and modern Python practices.**
