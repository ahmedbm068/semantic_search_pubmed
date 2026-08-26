#!/usr/bin/env bash
# Scrape NHS condition pages into data/scraped/nhs_conditions.jsonl.
# Usage: ./scripts/ingest.sh [max_items]
set -euo pipefail
cd "$(dirname "$0")/.."

MAX="${1:-50}"
python -c "from src.app.scraper.nhs_scraper import scrape_all; scrape_all(max_items=$MAX)"
