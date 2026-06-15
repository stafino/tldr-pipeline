.PHONY: install run refresh rank blurbs format backtest fmt test clean

DATE ?= $(shell date +%Y-%m-%d)
NEWSLETTER ?= tldr_founders

install:
	uv sync

refresh:
	uv run python -m ingestion.run --date $(DATE)
	uv run python -m dedup.run --date $(DATE)
	uv run python -m ranking.run --date $(DATE) --newsletter $(NEWSLETTER)
	uv run python -m blurbs.run --date $(DATE) --newsletter $(NEWSLETTER)
	uv run python -m formatters.tldr --date $(DATE) --newsletter $(NEWSLETTER)

ingest:
	uv run python -m ingestion.run --date $(DATE)

dedup:
	uv run python -m dedup.run --date $(DATE)

rank:
	uv run python -m ranking.run --date $(DATE) --newsletter $(NEWSLETTER)

blurbs:
	uv run python -m blurbs.run --date $(DATE) --newsletter $(NEWSLETTER)

format:
	uv run python -m formatters.tldr --date $(DATE) --newsletter $(NEWSLETTER)

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
