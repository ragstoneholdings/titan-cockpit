.PHONY: dev-api dev-web test docker-build docker-up

dev-api:
	.venv/bin/uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

dev-web:
	cd web && npm install && npm run dev

test:
	.venv/bin/python -m pytest tests/ -q

docker-build:
	docker build -t titan-cockpit-api:local .

docker-up:
	docker compose up --build
