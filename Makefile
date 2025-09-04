.PHONY: help dev-up dev-down migrate seed api-shell test lint format backup
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

dev-up: ## Start development environment
	docker-compose -f compose/docker-compose.yml -f compose/docker-compose.override.yml up -d

dev-down: ## Stop development environment
	docker-compose -f compose/docker-compose.yml -f compose/docker-compose.override.yml down

migrate: ## Run database migrations
	python manage.py migrate

seed: ## Load demo data
	python manage.py seed_demo

api-shell: ## Open Django shell
	python manage.py shell

test: ## Run tests with coverage
	pytest

lint: ## Run linting (pre-commit)
	pre-commit run --all-files

format: ## Format code
	black apps/
	isort apps/
	ruff --fix apps/

backup: ## Run database backup
	./scripts/backup_db.sh

clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .coverage

install: ## Install dependencies (development)
	pip install --upgrade pip
	pip install -r requirements/dev.txt
	pip install -e .
	pre-commit install

install-prod: ## Install production dependencies
	pip install --upgrade pip
	pip install -r requirements.txt

install-test: ## Install testing dependencies
	pip install --upgrade pip
	pip install -r requirements/test.txt

build: ## Build Docker image
	docker build -t django-saas-boilerplate .

logs: ## Show container logs
	docker-compose -f compose/docker-compose.yml logs -f

restart: ## Restart development environment
	make dev-down
	make dev-up

check: ## Run all checks (lint, test, type check)
	make lint
	make test
	mypy apps/