#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
from pathlib import Path
import os
import datetime as dt

# Optional: load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from rag.retriever import Retriever
from rag.generator import generate

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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="Path to Chroma DB directory")
    ap.add_argument("--topic", required=True, help="Topic keyword")
    ap.add_argument("--k", type=int, default=int(os.getenv("TOP_K", "5")), help="Top-k documents")
    ap.add_argument("--template", default="prompts/daily_ja.txt", help="Path to prompt template")
    ap.add_argument("--outdir", default=os.getenv("DRAFT_OUT_DIR", "storage/drafts"), help="Directory to store timestamped drafts")
    args = ap.parse_args()

    # Retrieve
    r = Retriever(args.db, top_k=args.k)
    hits = r.query(args.topic)
    context = render_context(hits)

    # Build prompt
    template = load_template(Path(args.template))
    prompt = template.format(topic=args.topic, context=context)

    # Generate
    out = generate(prompt)
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

