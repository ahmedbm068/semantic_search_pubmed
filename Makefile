run-api:
	uvicorn src.app.main:app --reload --port 8000
reindex:
	python -m src.app.index.build_index data/raw/pubmed_sample.csv
test:
	pytest -q
