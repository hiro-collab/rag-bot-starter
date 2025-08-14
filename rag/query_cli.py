# rag/query_cli.py
import argparse
from rag.retriever import Retriever
from rag.reranker import Reranker  # ← add
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
    
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--q", required=True)
    ap.add_argument("--k", type=int, default=8)
    # --- reranker options ---
    ap.add_argument("--rerank", action="store_true", help="Apply cross-encoder reranker")
    ap.add_argument("--rrk-top", type=int, default=None, help="Top-N after rerank (default=k)")
    ap.add_argument("--rrk-backend", default=None, help="ce (default) or bge")
    ap.add_argument("--rrk-model", default=None, help="Override model name")
    args = ap.parse_args()

    r = Retriever(args.db, top_k=args.k)
    hits = r.query(args.q)

    if args.rerank:
        rr = Reranker(model_name=args.rrk_model, backend=args.rrk_backend)
        hits = rr.rerank(args.q, hits, top_k=args.rrk_top or args.k)

    for i, h in enumerate(hits, 1):
        score = h.get("rerank_score")
        prefix = f"[{i}]"
        if score is not None:
            prefix += f" (rrk={score:.3f})"
        print(prefix, h.get("title") or h.get("day") or "", "-", (h.get("text") or "")[:120].replace("\n", " "))

if __name__ == "__main__":
    main()

