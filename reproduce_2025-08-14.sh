#!/usr/bin/env bash
# Reproduce today's RAG setup on bash (2025-08-14)
set -euo pipefail

export POETRY_CACHE_DIR="$PWD/.poetry-cache"
export PIP_CACHE_DIR="$PWD/.pip-cache"

poetry config virtualenvs.in-project true
pyenv local 3.13.5
poetry run python -V

poetry run python -m ingest.fetch_repo
poetry run python -m ingest.split_markdown --repo ./local_repo --out ./storage/chunks.jsonl
poetry run python -m ingest.build_index --chunks ./storage/chunks.jsonl --db ./storage/chroma

poetry run python -c "import chromadb; c=chromadb.PersistentClient(path='./storage/chroma'); print([col.name for col in c.list_collections()])"
poetry run python -m rag.query_cli --db ./storage/chroma --q '環境構築とは何か'

# (Optional)
# ollama pull qwen2.5:7b
# poetry run python -m rag.draft_today --db ./storage/chroma --topic '環境の勉強'
