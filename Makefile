.PHONY: help run test cov eval reindex lint docker clean

help:
	@echo "run      - start the dev server on :8000"
	@echo "test     - run the test suite"
	@echo "cov      - run tests with a coverage report"
	@echo "eval     - retrieval metrics across retriever configs"
	@echo "reindex  - rebuild the FAISS index from training pairs"
	@echo "lint     - ruff check"
	@echo "docker   - build and start the full stack"

run:
	uvicorn src.app.main:app --reload --port 8000

test:
	pytest

cov:
	pytest --cov=src/app --cov-report=term-missing

eval:
	python -m eval.eval_runner --n 300

reindex:
	bash scripts/rebuild_index.sh

lint:
	ruff check src tests eval

docker:
	docker compose up --build

clean:
	find . -type d -name __pycache__ -not -path "./.venv*/*" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache
