.PHONY: dev up down logs setup

# Development mode: hot reload for backend + frontend
# Auto-runs setup if .env is missing
dev:
	@if [ ! -f .env ]; then \
		echo "No .env file found — running setup..."; \
		python3 scripts/setup.py; \
	fi
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Production mode: pre-built images
up:
	docker compose up -d

# Stop all services
down:
	docker compose down

# Follow logs for all services
logs:
	docker compose logs -f

# Run setup script manually
setup:
	python3 scripts/setup.py
