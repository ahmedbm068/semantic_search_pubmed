#!/usr/bin/env bash
# Rebuild the FAISS index from the training pairs.
# Usage: ./scripts/rebuild_index.sh [model_dir]
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL="${1:-models/biomed-miniLM}"

echo "==> Flattening pairs into a corpus"
python -m src.app.index.make_corpus_from_pairs \
    --inputs data/processed/train_pairs.jsonl \
    --out data/raw/corpus.txt

echo "==> Embedding and indexing with $MODEL"
python -m src.app.index.build_index \
    --model-path "$MODEL" \
    --input data/raw/corpus.txt \
    --output-dir data/cache \
    --normalize

echo "==> Done. index_meta.json:"
cat data/cache/index_meta.json
