.PHONY: setup up down analytics orchestration dbt-build dbt-test migrate seed db-roles backup restore-drill test lint frontend-test demo-e2e e2e-sql-demo platform-check

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

db-roles:
	scripts/apply_db_roles.sh

backup:
	scripts/encrypted_pg_backup.sh

restore-drill:
	scripts/restore_drill.sh

simulate:
	docker compose exec -T api python -m backend.app.scripts.simulate_stream --duration-seconds 600 --interval-seconds 2

simulate-partner-e2e:
	docker compose exec -T api python -m backend.app.scripts.simulate_partner_e2e

demo-e2e:
	scripts/run_end_to_end_demo.sh

e2e-sql-demo:
	scripts/run_e2e_sql_demo.sh

platform-check:
	python3 scripts/platform_check.py

test:
	pytest -q

lint:
	ruff check backend tests
	cd frontend && npm run lint

frontend-test:
	cd frontend && npm test
