# ============================================================
# AKSHAY AI CORE — Makefile
# ============================================================
# Common commands for development and deployment.
# ============================================================

.PHONY: help install dev test lint format clean build run docker-build docker-up docker-down

# Default target
help:
	@echo "AKSHAY AI CORE - Available Commands"
	@echo "===================================="
	@echo ""
	@echo "Development:"
	@echo "  make install     - Install dependencies"
	@echo "  make dev         - Run development server"
	@echo "  make test        - Run tests"
	@echo "  make lint        - Run linting"
	@echo "  make format      - Format code"
	@echo ""
	@echo "Production:"
	@echo "  make build       - Build for production"
	@echo "  make run         - Run production server"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-up    - Start Docker containers"
	@echo "  make docker-down  - Stop Docker containers"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean       - Clean build artifacts"
	@echo "  make shell       - Start interactive shell"

# Install dependencies
install:
	pip install -e ".[dev]"
	playwright install chromium

# Run development server
dev:
	python main.py run --reload

# Run tests
test:
	pytest tests/ -v --cov=core --cov=api --cov=plugins

# Run linting
lint:
	ruff check .
	mypy core/ api/ plugins/

# Format code
format:
	ruff format .
	ruff check --fix .

# Clean build artifacts
clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	rm -rf build/ dist/ *.egg-info
	rm -rf htmlcov/ .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Build for production
build:
	python -m build

# Run production server
run:
	python main.py run --host 0.0.0.0 --port 8000

# Start interactive shell
shell:
	python main.py shell

# Initialize database
init:
	python main.py init

# Docker commands
docker-build:
	docker build -t akshay-ai-core .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f akshay

# Database migrations (if using Alembic)
migrate:
	alembic upgrade head

migrate-create:
	alembic revision --autogenerate -m "$(msg)"

# Generate documentation
docs:
	mkdocs build

docs-serve:
	mkdocs serve

# Security scan
security:
	bandit -r core/ api/ plugins/ -ll
	safety check
