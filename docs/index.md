# Django SaaS Boilerplate Documentation

Welcome to the Django SaaS Boilerplate documentation. This project provides a production-ready Django starter template with modern best practices.

## Quick Links

- [Quick Start](quickstart.md) - Get up and running in 5 minutes
- [Environment Variables](environment.md) - Configuration reference
- [Feature Flags](feature-flags.md) - Managing feature toggles
- [Email System](emails.md) - Template-based async emails
- [API Documentation](api.md) - REST API reference
- [Testing](testing.md) - Running tests and writing new ones
- [Deployment](deployment.md) - Production deployment guide

## Features Overview

- **🏗️ Modern Architecture**: Apps organized in `/apps/` for clear modular separation
- **📧 Async Emails**: Template-based emails via Celery with database storage
- **🏃‍♂️ Feature Flags**: `django-waffle` integration with management commands
- **👥 RBAC System**: Role-based access control with Django Groups
- **🔐 Authentication**: Custom user model with email login via `django-allauth`
- **🌐 REST API**: DRF with OpenAPI schema, Swagger UI, and versioning
- **🐳 Docker Ready**: Multi-service Docker Compose setup
- **🔍 Observability**: Sentry integration, health checks, and OpenTelemetry support

## Getting Help

- Check the documentation sections for detailed guides
- Open an issue on GitHub for bugs or feature requests
- Use GitHub Discussions for questions and community support

## Contributing

See our [Contributing Guide](contributing.md) for information on how to contribute to this project.
