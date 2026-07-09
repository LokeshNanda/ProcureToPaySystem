.PHONY: up down migrate seed-demo test lint

up:
	docker compose -f docker/docker-compose.yml up --build

down:
	docker compose -f docker/docker-compose.yml down

migrate:
	docker compose -f docker/docker-compose.yml run --rm api alembic upgrade head

seed-demo:
	docker compose -f docker/docker-compose.yml run --rm api python -m app.seed

test:
	cd backend && pytest -q
	cd frontend && npm run test --silent

lint:
	cd backend && ruff check . && mypy app
	cd frontend && npm run lint
