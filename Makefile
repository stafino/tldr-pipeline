.PHONY: install run refresh rank blurbs backtest fmt test clean

DATE ?= $(shell date +%Y-%m-%d)

install:
	uv sync

refresh:
	uv run python -m ingestion.run --date $(DATE)
	uv run python -m dedup.run --date $(DATE)
	uv run python -m ranking.run --date $(DATE)
	uv run python -m blurbs.run --date $(DATE)

ingest:
	uv run python -m ingestion.run --date $(DATE)

dedup:
	uv run python -m dedup.run --date $(DATE)

rank:
	uv run python -m ranking.run --date $(DATE)

blurbs:
	uv run python -m blurbs.run --date $(DATE)

run:
	uv run streamlit run ui/app.py

backtest:
	uv run python scripts/backtest.py --start 2026-06-01 --end 2026-06-12

fmt:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest tests/

clean:
	rm -rf data/raw/* data/deduped/* data/scored/* data/blurbs/*
