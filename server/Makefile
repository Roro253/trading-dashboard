run:
	poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	poetry run pytest -q

typecheck:
	poetry run mypy app

lint:
	poetry run ruff check app
