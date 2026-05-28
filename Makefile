.PHONY: setup up down analytics orchestration dbt-build dbt-test migrate seed backup test lint frontend-test

setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install -r requirements.txt
	cd frontend && npm install

up:
	docker compose up --build

down:
	docker compose down

analytics:
	docker compose --profile analytics up -d dbt superset

orchestration:
	docker compose --profile orchestration up -d airflow

dbt-build:
	docker compose --profile analytics run --rm dbt build

dbt-test:
	docker compose --profile analytics run --rm dbt test

migrate:
	alembic -c backend/alembic.ini upgrade head

seed:
	python -m backend.app.scripts.seed

backup:
	scripts/encrypted_pg_backup.sh

simulate:
	docker compose exec -T api python -m backend.app.scripts.simulate_stream --duration-seconds 600 --interval-seconds 2

simulate-partner-e2e:
	docker compose exec -T api python -m backend.app.scripts.simulate_partner_e2e

test:
	pytest -q

lint:
	ruff check backend tests
	cd frontend && npm run lint

frontend-test:
	cd frontend && npm test
