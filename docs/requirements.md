# Requirements Management

This project uses a structured approach to dependency management with separate requirements files for different environments.

## Requirements Structure

```
requirements/
├── base.txt        # Core dependencies (Django, DRF, Celery, etc.)
├── dev.txt         # Development tools (testing, linting, debugging)
├── prod.txt        # Production-specific packages
└── test.txt        # Testing-only dependencies
requirements.txt    # Main file (points to production requirements)
```

## Installation

### Development Environment

For local development with all tools:

```bash
# Using Make (recommended)
make install

# Or manually
pip install --upgrade pip
pip install -r requirements/dev.txt
pip install -e .
```

### Production Environment

For production deployment:

```bash
# Using Make
make install-prod

# Or manually
pip install --upgrade pip
pip install -r requirements.txt
```

### Testing Environment

For running tests only:

```bash
# Using Make
make install-test

# Or manually
pip install --upgrade pip
pip install -r requirements/test.txt
```

## Requirements Files Explained

### base.txt

Core dependencies required in all environments:

- **Django Framework**: Core Django and DRF
- **Authentication**: django-allauth for user management
- **Background Tasks**: Celery with Redis
- **Database**: PostgreSQL driver (psycopg)
- **File Storage**: S3/MinIO support via boto3
- **Monitoring**: Sentry, OpenTelemetry
- **Production Server**: Gunicorn
- **Utilities**: Environment handling, feature flags

### dev.txt

Development-specific tools (includes base.txt):

- **Code Quality**: ruff, black, isort, pre-commit
- **Type Checking**: mypy with Django stubs
- **Security**: bandit, pip-audit
- **Testing**: pytest with plugins
- **Development Tools**: django-extensions, ipython, ipdb
- **Documentation**: mkdocs

### prod.txt

Production optimizations (includes base.txt):

- **Storage Backends**: django-storages for cloud storage
- **Performance**: Database connection pooling
- **Health Checks**: Enhanced health check endpoints
- **Security**: Additional production security packages

### test.txt

Testing-focused minimal setup (includes base.txt):

- **Core Testing**: pytest with essential plugins
- **Test Data**: factory-boy for test fixtures
- **Mocking**: freezegun, responses
- **Code Quality**: Basic linting for CI
- **Security Testing**: bandit for vulnerability scanning

## Docker Integration

### Development

Uses `Dockerfile.dev` which installs development requirements:

```dockerfile
# Install development requirements
RUN pip install --no-cache-dir -r requirements/dev.txt
```

### Production

Uses `Dockerfile` which installs production requirements:

```dockerfile
# Install production requirements
RUN pip install --no-cache-dir -r requirements.txt
```

## CI/CD Integration

GitHub Actions uses different requirements for different jobs:

- **Linting**: Development requirements for all tools
- **Testing**: Test requirements for minimal setup
- **Security**: Test requirements for security scanning
- **Docker Build**: Production requirements

## Dependency Updates

### Automated Updates

Consider using dependabot or similar tools:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/requirements"
    schedule:
      interval: "weekly"
```

### Manual Updates

To update dependencies:

```bash
# Check for outdated packages
pip list --outdated

# Update specific package in requirements file
# Then reinstall
make install

# Run tests to ensure compatibility
make test
```

### Security Updates

Regular security scanning:

```bash
# Scan for vulnerabilities
pip-audit

# Update security-related packages immediately
pip install --upgrade django celery sentry-sdk
```

## Alternative: pyproject.toml

The project also includes `pyproject.toml` for compatibility with modern Python tooling:

- **Development**: `pip install -e .[dev]`
- **Production**: `pip install -e .`

Both approaches work, choose based on your deployment needs:

- **requirements.txt**: Better for traditional deployments, Docker
- **pyproject.toml**: Better for modern Python tooling, local development

## Environment-Specific Notes

### Development

- Includes debugging tools (ipdb, django-extensions)
- Pre-commit hooks for code quality
- Documentation generation tools
- All testing and linting tools

### Production

- Optimized for performance and security
- No development tools included
- Enhanced monitoring and health checks
- Production-ready storage backends

### Testing

- Minimal setup for fast CI/CD
- Essential testing tools only
- Basic code quality tools
- Security vulnerability scanning

## Troubleshooting

### Common Issues

**Dependency Conflicts:**
```bash
# Clean install
pip uninstall -r requirements/dev.txt -y
pip install -r requirements/dev.txt
```

**Missing System Dependencies:**
```bash
# Ubuntu/Debian
apt-get install build-essential libpq-dev

# macOS
brew install postgresql
```

**Docker Build Issues:**
```bash
# Clear Docker cache
docker system prune -a
docker build --no-cache -t django-saas-boilerplate .
```

### Version Pinning

Requirements are pinned to major versions for stability:

- **Flexible**: `>=4.2,<5.0` (allows patch/minor updates)
- **Strict**: `==4.2.7` (exact version, use for critical packages)
- **Minimum**: `>=4.2.0` (minimum version required)

Choose pinning strategy based on stability needs vs. security updates.
