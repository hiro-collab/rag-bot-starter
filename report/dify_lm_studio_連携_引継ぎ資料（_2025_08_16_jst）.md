# Dify × LM Studio 連携・引継ぎ資料（2025-08-16 / Windows 11 + PowerShell）

> 目的：**ローカルの Dify（Docker）と LM Studio（OpenAI互換API）を接続し、Pythonクライアントから安定して呼べる状態**を再現できるように、手順・設定・トラブルシュートを一枚にまとめる。関係者への引継ぎ用。

---

## 0. 到達点（この資料のゴール）

- Dify コンソールが [**http://localhost:8080**](http://localhost:8080) で表示（Nginx: 8080→80）。
- Dify の **Apps** で対象アプリ作成済み、**App API Key（**``**）** を発行済み。
- **Model Providers → OpenAI API Compatible** にて、**Base URL = **``（ホストで動く LM Studio を Docker 内から参照）で接続。モデルは `/v1/models` に出る **id** を選択。
- LM Studio 側は **Server 起動**＋**モデルを最低1つロード**済み（例：`google/gemma-3-12b:2 Q4_0`）。
- Python（Poetry）から \*\*SSE（行バッファ）\*\*で受信・表示できるサンプルが動作。

---

## 1. 構成（ざっくり）

```
[Python client (Poetry)] --HTTP--> [Nginx in Dify Docker] --> /v1/* (Service API)
                                            |
                                            +--> [Model Providers: OpenAI-compatible] --HTTP--> [LM Studio server]
```

- ポート：ホスト `8080` → Nginx(80)。必要なら `https://localhost`(443, 自己署名) も可（後述）。
- Dify API は **Nginx 経由の 8080** を使う（`api:5001` を直接叩かない）。
- Dify→LM Studio は `` を使ってホストへ到達。

---

## 2. 前提（バージョン/環境）

- OS: Windows 11, PowerShell 7 推奨
- Docker Desktop（WSL2 バックエンド）
- Dify: Docker 構成（例：`dify-api:1.5.x`）
- LM Studio: Desktop アプリ（Server 起動機能を使用）
- Python: 3.12.x（pyenv-win）
- パッケージ管理：Poetry（アプリ側）、**uv 併用可**（ユーティリティ）

---

## 3. セットアップ手順（再現用）

### 3.1 Dify スタック起動

```powershell
# comments: English
cd .\dify\docker
Copy-Item .env.example .env  # 必要に応じて修正
# 起動
docker compose up -d
# ポートと状態確認
docker compose ps
```

- ブラウザで [**http://localhost:8080**](http://localhost:8080) を開く。

### 3.2 App API Key の発行

1. Dify コンソール → **Apps** → 対象アプリを選択。
2. **API Access** → **Create** でキーを作成（`app-...`）。
3. これを **Python や PowerShell の環境変数**に設定。

### 3.3 LM Studio 側の準備

- **Models** でモデルをダウンロード→**Developer → Start Server**（デフォルト `http://127.0.0.1:1234/v1`）。
- **Loaded models** に最低1つ表示されていること。
- 動作確認（任意）：

```powershell
# comments: English
Invoke-RestMethod -Uri "http://127.0.0.1:1234/v1/models" -Headers @{ Authorization = "Bearer lm-studio" }
```

### 3.4 Dify の Model Provider 設定

- **Settings → Model Providers → OpenAI API Compatible** を追加/編集。
  - **Base URL**：`http://host.docker.internal:1234/v1`
  - **API Key**：任意文字列（例：`lm-studio`）
  - **Model**：LM Studio の `/v1/models` に出る **id** と一致させる。
- 各アプリの **Model & Parameters** で、この Provider / Model を選び **保存**。

### 3.5 .env（クライアント用）

```ini
DIFY_API_BASE=http://localhost:8080
DIFY_API_KEY=app-xxxxxxxxxxxxxxxxxxxxxxxx
DIFY_USER_ID=kawai-local-01
```

> **注意**：Gitにコミットしない（漏洩時は Dify 側で Revoke）。

### 3.6 Python クライアント（SSE 行バッファ版）

```python
# main.py
# comments: English
import os, json, re
import httpx
from dotenv import load_dotenv

TAG_RE = re.compile(r"<\|[^>]+?\|>\s*")  # remove control tags like <|channel|>final

def clean_text(s: str) -> str:
    return TAG_RE.sub("", s or "")

def ascii_only(s: str) -> str:
    return s.encode("ascii", "ignore").decode().strip()

def main():
    load_dotenv()
    api_base = os.getenv("DIFY_API_BASE", "http://localhost:8080").rstrip("/")
    api_key  = ascii_only(os.getenv("DIFY_API_KEY", ""))
    user_id  = os.getenv("DIFY_USER_ID", "handover-user")
    if not api_key:
        raise RuntimeError("DIFY_API_KEY is missing")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "text/event-stream",
    }
    payload = {
        "query": "ping from handover doc",
        "inputs": {},
        "response_mode": "streaming",
        "user": user_id,
    }

    timeout = httpx.Timeout(connect=5.0, read=300.0, write=10.0, pool=5.0)

    line_buf = ""
    def flush_linebuf():
        nonlocal line_buf
        text = line_buf.strip()
        if text:
            print("message", text)
        line_buf = ""

    with httpx.Client(timeout=timeout) as client:
        with client.stream("POST", f"{api_base}/v1/chat-messages", headers=headers, json=payload) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():  # str lines
                if not line or not line.startswith("data: "):
                    continue
                data_part = line[6:]
                if data_part == "[DONE]":
                    break
                try:
                    evt = json.loads(data_part)
                except json.JSONDecodeError:
                    continue

                event = evt.get("event")
                if event in ("workflow_started", "node_started", "node_finished", "workflow_finished"):
                    print(event)
                    if event == "workflow_finished":
                        flush_linebuf()
                    continue

                if event == "message":
                    delta = clean_text(evt.get("answer") or evt.get("message") or "")
                    if not delta:
                        continue
                    line_buf += delta.replace("\r\n", "\n")
                    while "\n" in line_buf:
                        out, line_buf = line_buf.split("\n", 1)
                        if out.strip():
                            print("message", out.strip())

                elif event in ("message_end", "completed", "task_error"):
                    flush_linebuf()
                    print(event)
                    if event == "task_error":
                        err = (evt.get("message") or "").strip()
                        if err:
                            print("error", err)

if __name__ == "__main__":
    main()
```

---

## 4. 運用（スタート/テスト/停止）

- 起動：`docker compose up -d` / 停止：`docker compose down`
- コンソール：`http://localhost:8080`（HTTPS を使う場合は自己署名の設定が必要。後述）
- API テスト（PowerShell）

```powershell
# comments: English
$env:DIFY_API_BASE = "http://localhost:8080"
$env:DIFY_API_KEY  = "app-xxxxxxxxxxxxxxxx"
$userId = "handover-user"
$body = @{ query = "ping"; inputs=@{}; response_mode="blocking"; user=$userId } | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri "$env:DIFY_API_BASE/v1/chat-messages" -Headers @{ Authorization = "Bearer $env:DIFY_API_KEY" } -ContentType "application/json" -Body $body
```

---

## 5. トラブルシュート（頻出）

- `` → ボディに `user` を必ず入れる。
- `` → APIキーに全角や不可視文字が混入。**ASCII化**し直す（`ascii_only()` 参照）。
- ``**（404/model\_not\_found）** → LM Studio で **モデル未ロード**。GUIでロードor `lms run ...`。`/v1/models` で存在確認。
- `` → `httpx.Timeout` の `read` を延長 or `` に変更。
- ``** で繋がらない** → 自己署名の証明書が未設定。ローカルは **8080(HTTP)** 推奨。HTTPS化するなら `mkcert` 等で証明書を作成し、Nginx の `ssl_certificate` を差し替えて再起動。
- ``** を Dify→LM Studio 間で使っている** → コンテナからの `localhost` はコンテナ自身。`` を使う。

---

## 6. 受け入れ基準（ハンドオーバーチェック）

-

---

## 7. セキュリティ & 運用メモ

- `.env` はバージョン管理から除外。漏洩時は **Revoke → 再発行**。
- 企業プロキシ/SSL検査がある場合は、Poetry/uv の **証明書設定**や **ミラー**を使用。
- ログ確認：`docker logs -f docker-api-1` / `docker logs -f docker-worker-1` / LM Studio サーバーログ。

---

## 8. HTTPS 化（必要時）

1. `mkcert` などで `localhost` 証明書を作成。
2. `docker/nginx` の設定で `ssl_certificate`/`ssl_certificate_key` を発行物に変更し、`volumes` でマウント。
3. `docker compose down && up -d`。クライアント側検証は **開発時のみ **`` で回避可（本番NG）。

---

## 付録：ワンポイントコマンド集

```powershell
# Dify 起動/停止
cd .\dify\docker
docker compose up -d
docker compose down

# ポート確認
netstat -ano | findstr ":8080"

# LM Studio モデル一覧（疎通）
Invoke-RestMethod -Uri "http://127.0.0.1:1234/v1/models" -Headers @{ Authorization = "Bearer lm-studio" }

# Dify API テスト（Streaming ではなく Blocking）
$env:DIFY_API_BASE = "http://localhost:8080"
$env:DIFY_API_KEY  = "app-xxxxxxxxxxxxxxxx"
$userId = "handover-user"
$body = @{ query = "hello"; inputs=@{}; response_mode="blocking"; user=$userId } | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri "$env:DIFY_API_BASE/v1/chat-messages" -Headers @{ Authorization = "Bearer $env:DIFY_API_KEY" } -ContentType "application/json" -Body $body
```

