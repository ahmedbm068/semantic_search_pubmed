#!/usr/bin/env bash
# Run the retrieval evaluation across retriever configurations.
# Usage: ./scripts/eval.sh [n_queries]
set -euo pipefail
cd "$(dirname "$0")/.."

N="${1:-300}"
python -m eval.eval_runner \
    --n "$N" \
    --configs dense bm25 hybrid:0.3 hybrid:0.5 hybrid:0.7 \
    --json-out eval/results.json
