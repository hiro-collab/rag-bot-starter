# Reproduce today's RAG setup on Windows PowerShell (2025-08-14)
# NOTE: Run from the project root (rag-bot-starter)

# --- Use project-local caches to avoid AppData restrictions ---
$env:POETRY_CACHE_DIR = "$pwd\.poetry-cache"
$env:PIP_CACHE_DIR    = "$pwd\.pip-cache"

# --- Poetry env ---
poetry config virtualenvs.in-project true
pyenv local 3.13.5
poetry run python -V

# --- Fetch repo ---
poetry run python -m ingest.fetch_repo

# --- Chunk & Index ---
poetry run python -m ingest.split_markdown --repo .\local_repo --out .\storage\chunks.jsonl
poetry run python -m ingest.build_index --chunks .\storage\chunks.jsonl --db .\storage\chroma

# --- Verify ---
poetry run python -c "import chromadb; c=chromadb.PersistentClient(path=r'.\storage\chroma'); print([col.name for col in c.list_collections()])"

# --- Query test ---
poetry run python -m rag.query_cli --db .\storage\chroma --q "環境構築とは何か"

# --- (Optional) Generation via Ollama ---
# ollama pull qwen2.5:7b
# poetry run python -m rag.draft_today --db .\storage\chroma --topic "環境の勉強"
