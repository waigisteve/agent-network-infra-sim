.PHONY: setup up down migrate seed test lint frontend-test

setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install -r requirements.txt
	cd frontend && npm install

up:
	docker compose up --build

down:
	docker compose down

migrate:
	alembic -c backend/alembic.ini upgrade head

seed:
	python -m backend.app.scripts.seed

simulate:
	docker compose exec -T api python -m backend.app.scripts.simulate_stream --duration-seconds 600 --interval-seconds 2

test:
	pytest -q

lint:
	ruff check backend tests
	cd frontend && npm run lint

frontend-test:
	cd frontend && npm test
