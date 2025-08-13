# RAG Bot Starter

このスターターは、`days/` 配下のMarkdownをRAGデータベース化し、
まずはローカルで検索→下書き生成まで動かす最小構成です。
配信（Slack/X/Gmail）や承認UIは **後で足す** 前提。

## 0) 前提
- Python 3.10 以降（3.11 推奨）
- `git` が使えること
- OS: Ubuntu / WSL2 / macOS / Windows（PowerShell）

## 1) 仮想環境 & 依存インストール
```bash
# Unix (Ubuntu/WSL2)
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
cp .env.example .env
```

```powershell
# Windows PowerShell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
copy .env.example .env
```

## 2) days リポジトリの同期
`.env` の `GIT_REPO_URL` と `LOCAL_REPO_DIR` を設定してから：
```bash
python ingest/fetch_repo.py
```

## 3) チャンク化 → ベクトルDB作成
```bash
python ingest/split_markdown.py --repo $LOCAL_REPO_DIR --out storage/chunks.jsonl
python ingest/build_index.py --chunks storage/chunks.jsonl --db $CHROMA_DIR
```

## 4) 検索テスト
```bash
python rag/query_cli.py --db $CHROMA_DIR --q "環境構築とは何か"
```

## 5) 生成テスト（ローカルLLM or OpenAI）
`.env` に LM Studio / Ollama / OpenAI のいずれかを設定してから：
```bash
python rag/draft_today.py --db $CHROMA_DIR --topic "環境の勉強"
```

---
次のステップ：
- Slack 承認フロー（Block Kit & slash command）
- APScheduler で 09:00 / 13:00 / 20:00 のドラフト作成
- X/Gmail 送信アダプタ
