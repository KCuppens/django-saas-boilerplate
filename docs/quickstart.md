# Quick Start Guide

Get your Django SaaS Boilerplate up and running in 5 minutes.

## Prerequisites

- Python 3.11 or higher
- Git
- Docker & Docker Compose (recommended)

## Option 1: Docker Setup (Recommended)

### 1. Clone and Configure

```bash
git clone https://github.com/yourusername/django-saas-boilerplate.git
cd django-saas-boilerplate

# Copy environment file
cp .env.example .env
```

### 2. Start Services

```bash
# Start all services (API, database, Redis, etc.)
make dev-up

# Wait for services to be ready (about 30 seconds)
```

### 3. Initialize Database

```bash
# Run migrations
make migrate

# Create user groups and permissions
docker-compose exec api python manage.py sync_groups

# Create feature flags
docker-compose exec api python manage.py sync_flags

# Load demo data
make seed
```

### 4. Verify Installation

```bash
# Check health
curl http://localhost:8000/healthz

# Visit Swagger UI
open http://localhost:8000/schema/swagger/

# Check email testing interface
open http://localhost:8025
```

## Option 2: Local Development Setup

### 1. Install Dependencies

```bash
# Install Python dependencies
make install

# Start supporting services only
docker-compose up -d postgres redis mailpit
```

### 2. Configure Environment

```bash
# Copy and edit environment file
cp .env.example .env

# Edit .env file:
# - Set DATABASE_URL for PostgreSQL or leave default for SQLite
# - Configure other services as needed
```

### 3. Initialize Application

```bash
# Run migrations
python manage.py migrate

# Create groups and flags
python manage.py sync_groups
python manage.py sync_flags

# Load demo data
python manage.py seed_demo
```

### 4. Start Development Servers

```bash
# Terminal 1: Django development server
python manage.py runserver

# Terminal 2: Celery worker
celery -A apps.config worker -l info

# Terminal 3: Celery beat (optional)
celery -A apps.config beat -l info
```

## What's Next?

### 1. Explore the API

- **Swagger UI**: http://localhost:8000/schema/swagger/
- **ReDoc**: http://localhost:8000/schema/redoc/
- **Health Check**: http://localhost:8000/healthz

### 2. Test Authentication

Use the demo accounts created by `seed_demo`:

- **Admin**: `admin@example.com` / `demo123`
- **Manager**: `manager@example.com` / `demo123`
- **Member**: `member@example.com` / `demo123`

### 3. Try the Notes API

```bash
# Register a new user
curl -X POST http://localhost:8000/api/v1/auth/users/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password1": "mypassword123",
    "password2": "mypassword123",
    "name": "Test User"
  }'

# Create a note (after login)
curl -X POST http://localhost:8000/api/v1/notes/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Note",
    "content": "This is a test note",
    "is_public": true
  }'
```

### 4. Check Email Templates

In development, email templates can be previewed at:
- http://localhost:8000/dev/emails/

### 5. Admin Interface

Access the Django admin at:
- http://localhost:8000/admin/
- Use the admin demo user: `admin@example.com` / `demo123`

## Troubleshooting

### Services Won't Start

```bash
# Check service logs
docker-compose logs api
docker-compose logs postgres

# Restart services
make dev-down
make dev-up
```

### Database Issues

```bash
# Reset database
docker-compose down -v
docker-compose up -d postgres redis
make migrate
make seed
```

### Permission Issues

```bash
# Re-sync groups and permissions
python manage.py sync_groups --force
```

### Clear Cache

```bash
# Clear Redis cache
docker-compose exec redis redis-cli FLUSHALL
```

## Next Steps

- Read the [API Documentation](api.md)
- Learn about [Feature Flags](feature-flags.md)
- Set up [Email Templates](emails.md)
- Configure for [Production Deployment](deployment.md)
