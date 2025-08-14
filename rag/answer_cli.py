# Q&A CLI using existing Retriever / (optional) Reranker / generator
import argparse
from pathlib import Path
from typing import List, Dict
from rag.retriever import Retriever
from rag.generator import generate
try:
    from rag.reranker import Reranker
except Exception:
    Reranker = None  # optional
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
    
# Build concise context bullets from hits
def render_context(hits: List[Dict], limit: int = 4) -> str:
    # take top N hits and trim text
    lines = []
    for h in hits[:limit]:
        title = (h.get("title") or h.get("day") or "") if isinstance(h, dict) else ""
        head = f"{title} - " if title else ""
        text = (h.get("text") or "").strip().replace("\n", " ")
        lines.append(f"- {head}{text[:500]}")
    return "\n".join(lines)

# Simple Japanese QA prompt (関西め・常体、具体手順)
QA_TEMPLATE = """あなたは技術質問に日本語で答える編集者や。関西弁を少し混ぜ、語尾は常体。前置き禁止、出力のみ。
過去記録（コンテキスト）を最大限使い、事実は簡潔に。手順は箇条書きで最大5個。危険操作（削除/初期化/上書き/アンインストール/レジストリ変更）は提案しない。

# 質問
{question}

# コンテキスト
{context}

# 出力要件
- まず結論を1〜2文
- 次に手順（最大5）
- 最後に注意点があれば1行
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--q", required=True, help="Question in Japanese")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--rerank", action="store_true", help="Apply reranker if available")
    ap.add_argument("--rrk-backend", default=None, help="ce or bge (optional)")
    ap.add_argument("--rrk-model", default=None, help="override reranker model")
    ap.add_argument("--rrk-top", type=int, default=None, help="take top-N after rerank")
    ap.add_argument("--show-sources", action="store_true", help="print source titles")
    args = ap.parse_args()

    # Retrieve
    r = Retriever(args.db, top_k=args.k)
    hits = r.query(args.q)

    # Optional rerank
    if args.rerank and Reranker is not None and hits:
        rr = Reranker(model_name=args.rrk_model, backend=args.rrk_backend)
        hits = rr.rerank(args.q, hits, top_k=args.rrk_top or args.k)

    # Build prompt and generate
    context = render_context(hits)
    prompt = QA_TEMPLATE.format(question=args.q, context=context)
    out = generate(prompt)

    print(out.strip())

    if args.show_sources and hits:
        print("\n--- sources ---")
        for i, h in enumerate(hits[: args.rrk_top or args.k], 1):
            title = h.get("title") or h.get("day") or "(no title)"
            print(f"[{i}] {title}")

if __name__ == "__main__":
    main()
