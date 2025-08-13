import os
import requests
from typing import List, Dict

# Very small abstraction for generation backends.
# It tries LM Studio -> Ollama -> OpenAI (if keys/urls exist).

def _gen_lmstudio(prompt: str, model: str, base_url: str) -> str:
    # LM Studio-compatible OpenAI API
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role":"user","content": prompt}],
        "temperature": 0.7,
    }
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def _gen_ollama(prompt: str, model: str, base_url: str) -> str:
    url = f"{base_url}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role":"user","content": prompt}],
        "stream": False
    }
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["message"]["content"]

def _gen_openai(prompt: str, api_key: str) -> str:
    # Minimal OpenAI Chat Completions (legacy). Replace with your preferred SDK if needed.
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role":"user","content": prompt}],
        "temperature": 0.7,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def generate(prompt: str) -> str:
    lmstudio_url = os.getenv("LMSTUDIO_BASE_URL")
    lmstudio_model = os.getenv("LMSTUDIO_MODEL", "Qwen2.5-7B-Instruct")
    if lmstudio_url:
        try:
            return _gen_lmstudio(prompt, lmstudio_model, lmstudio_url)
        except Exception:
            pass

    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    try:
        return _gen_ollama(prompt, ollama_model, ollama_url)
    except Exception:
        pass

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return _gen_openai(prompt, api_key)

    return "【生成バックエンド未設定】.env を確認してください。"
