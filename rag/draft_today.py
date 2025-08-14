#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
from pathlib import Path
import os
import datetime as dt
import re
# from rag.retriever import Retriever
# from rag.generator import generate
# ... and ensure enforce_length(...) is defined/imported above main()
# Optional: load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
# Silence Hugging Face transformers advisory logs
try:
    # v4系: utils.logging API
    from transformers.utils.logging import set_verbosity_error
    set_verbosity_error()
except Exception:
    try:
        # fallback for older versions
        import transformers
        transformers.logging.set_verbosity_error()
    except Exception:
        pass
    
from rag.retriever import Retriever
from rag.generator import generate
from rag.reranker import Reranker

# Default inline template (fallback)
DEFAULT_TEMPLATE = """あなたは日本語で短い技術エッセイを書くライターです。関西弁で、300〜600字。
出力のみ返す。前置きや説明は禁止。
次の素材（過去の知見）を1〜3個ほど引用しつつ、「今日の問い」「過去知見」「今日の一歩」の3段で構成してください。
なるべく曖昧表現を避け、読者が真似できる行動を1つ具体に書くこと。
---
テーマ: {topic}

素材:
{context}
"""

def load_template(path: Path) -> str:
    """Load a template file if exists, otherwise return the default."""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return DEFAULT_TEMPLATE

def render_context(hits):
    """Build bullet-point snippets with optional metadata."""
    lines = []
    for h in hits:
        # meta may or may not exist
        t = (h.get("title") or h.get("day") or "") if isinstance(h, dict) else ""
        s = (h.get("section") or h.get("heading") or "") if isinstance(h, dict) else ""
        head = " / ".join([x for x in [str(t), str(s)] if x])
        text = (h["text"] if isinstance(h, dict) else str(h)).strip().replace("\n", " ")[:300]
        lines.append(f"- {head + ' - ' if head else ''}{text}")
    return "\n\n".join(lines)

def enforce_length(prompt: str, text: str, min_chars=300, max_chars=600) -> str:
    """Ensure output length is within [min,max]; try one controlled regeneration if not."""
    # count characters excluding newlines
    def clen(s: str) -> int:
        return len(s.replace("\n", ""))

    t = text.strip()
    n = clen(t)
    if min_chars <= n <= max_chars:
        return t

    # Try one more generation with an explicit constraint
    tightened = (
        prompt
        + f"\n\n# 制約: 出力は本文のみ。前置き禁止。{min_chars}〜{max_chars}字に収めて再構成せよ。"
    )
    t2 = generate(tightened).strip()
    n2 = clen(t2)
    if min_chars <= n2 <= max_chars:
        return t2

    # As a last resort: hard trim if too long; keep original if too short.
    return (t2 if n2 >= min_chars else t)[:max_chars]



# --- helpers: extract only the "one step" section ---
def extract_one_step(text: str) -> str:
    """
    Try to extract the '今日やる一歩' section (heuristic).
    Looks for headings like '今日やる一歩', '一歩:', '3)' etc.
    """
    lines = [ln.strip() for ln in text.splitlines()]
    # patterns to detect the beginning of the step section
    start_pat = re.compile(r"(今日やる一歩|一歩[:：]|^\s*3\)|^\s*3\.)")
    started = False
    buf = []
    for ln in lines:
        if not started and start_pat.search(ln):
            started = True
            buf.append(ln)
            continue
        if started:
            # stop if next major block likely starts
            if re.match(r"^(問い[:：]|知見[:：]|^\s*\d[\).\:]|\s*#)", ln):
                break
            buf.append(ln)
    return "\n".join(buf) if buf else ""

def contains_dangerous_ops(text: str) -> bool:
    """
    Detect destructive ops in Japanese or English.
    """
    t = text.lower()
    # English command-like terms
    en = [
        r"\brm\b", r"\brmdir\b", r"\bdel\b", r"\bformat\b", r"\bwipe\b",
        r"\bdrop\s+table\b", r"pip\s+uninstall", r"pyenv\s+uninstall",
        r"conda\s+remove", r"rd\s+/s", r"reg\s+delete"
    ]
    # Japanese terms (loose)
    ja = [ "削除", "消去", "消す", "アンインストール", "初期化", "上書き", "破棄", "廃棄" ]
    if any(re.search(p, t, flags=re.IGNORECASE) for p in en):
        return True
    # check Japanese in original casing
    if any(k in text for k in ja):
        return True
    return False

def sanitize_step_fulltext(full_text: str) -> bool:
    """
    Check only the 'one step' section if available; fallback to full text.
    Return True if destructive ops are found.
    """
    step = extract_one_step(full_text) or full_text
    return contains_dangerous_ops(step)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="Path to Chroma DB directory")
    ap.add_argument("--topic", required=True, help="Topic keyword")
    ap.add_argument("--k", type=int, default=int(os.getenv("TOP_K", "5")), help="Top-k documents")
    ap.add_argument("--template", default="prompts/daily_ja.txt", help="Path to prompt template")
    ap.add_argument("--outdir", default=os.getenv("DRAFT_OUT_DIR", "storage/drafts"), help="Directory to store timestamped drafts")
    ap.add_argument("--rerank", action="store_true", help="Apply cross-encoder reranker before building context")
    ap.add_argument("--rrk-top", type=int, default=None, help="Top-N after rerank (default=k)")
    ap.add_argument("--rrk-backend", default=None, help="ce (default) or bge")
    ap.add_argument("--rrk-model", default=None, help="Override model name")
    args = ap.parse_args()

    # Retrieve
    r = Retriever(args.db, top_k=args.k)
    hits = r.query(args.topic)
    if args.rerank:
        rr = Reranker(model_name=args.rrk_model, backend=args.rrk_backend)
        hits = rr.rerank(args.topic, hits, top_k=args.rrk_top or args.k)
    context = render_context(hits)

    # Build prompt
    template = load_template(Path(args.template))
    prompt = template.format(topic=args.topic, context=context)

    # Generate (1st pass)
    out = generate(prompt)

    # Safety check → regenerate once if needed
    if sanitize_step_fulltext(out):
        tightened = (
            prompt +
            "\n\n# 制約: 破壊的操作（削除/アンインストール/初期化/上書き/レジストリ変更等）は禁止。"
            "新規ディレクトリや仮想環境での検証手順、バックアップ作成、--dry-runの提示に切り替えて出力せよ。"
            "出力のみ返す。前置き禁止。"
        )
        out = generate(tightened)

        # second guard: if still dangerous, replace the step block with a safe boilerplate
        if sanitize_step_fulltext(out):
            # Soft replace: append safe instructions at the end
            safe_boiler = (
                "\n\n---\n"
                "【安全な一歩】\n"
                "新規作業用フォルダを作る→仮想環境で依存を追加→動作確認のみ実施：\n"
                "PowerShell:\n"
                "mkdir env_demo; cd env_demo; poetry new demo --name demo; cd demo; "
                "poetry add requests; poetry run python -c \"import requests;print(requests.__version__)\""
            )
            out = out.strip() + safe_boiler

    # Enforce length (300–600 chars, excluding newlines)
    out = enforce_length(prompt, out, min_chars=300, max_chars=600)

    # Save (history + last_draft)
    Path("storage/logs").mkdir(parents=True, exist_ok=True)
    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = "".join([c for c in args.topic if c.isalnum()])[:24] or "topic"
    hist_path = Path(args.outdir) / f"{ts}_{safe_topic}.txt"
    hist_path.write_text(out, encoding="utf-8")

    Path("storage/logs/last_draft.txt").write_text(out, encoding="utf-8")

    print(out)
    print(f"\n[Saved] {hist_path}")

if __name__ == "__main__":
    main()

