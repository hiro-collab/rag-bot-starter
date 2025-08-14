# rag/reranker.py
from typing import List, Dict, Optional
import os

# Try sentence-transformers first (lightweight CrossEncoder)
try:
    from sentence_transformers import CrossEncoder
except Exception as e:
    CrossEncoder = None

# Optional: FlagEmbedding backend for BGE reranker
try:
    from FlagEmbedding import FlagReranker  # pip install FlagEmbedding
except Exception:
    FlagReranker = None


def _hit_text(hit: dict) -> str:
    """Extract textual content from a hit dict."""
    if isinstance(hit, dict):
        t = hit.get("text") or hit.get("document") or ""
        return str(t)
    return str(hit)


class Reranker:
    """
    Pluggable reranker:
      - backend='ce' uses sentence-transformers CrossEncoder (default)
      - backend='bge' uses FlagEmbedding BAAI/bge-reranker-*
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        backend: Optional[str] = None,
        device: Optional[str] = None,
        max_length: int = 512,
    ) -> None:
        # Resolve backend/model from env or defaults
        self.backend = (backend or os.getenv("RERANKER_BACKEND") or "ce").lower()
        self.model_name = model_name or os.getenv("RERANKER_MODEL") or (
            "cross-encoder/ms-marco-MiniLM-L-6-v2" if self.backend == "ce"
            else "BAAI/bge-reranker-v2-m3"
        )
        self.device = device or os.getenv("RERANKER_DEVICE")  # e.g., 'cuda' or 'cpu'
        self.max_length = max_length

        if self.backend == "bge":
            if FlagReranker is None:
                raise ImportError("FlagEmbedding is not installed. Try: pip install FlagEmbedding")
            # use_fp16=True is fine on CUDA; it falls back on CPU if no GPU
            self.model = FlagReranker(self.model_name, use_fp16=(self.device == "cuda"))
            self._predict = self._predict_bge
        else:
            if CrossEncoder is None:
                raise ImportError("sentence-transformers is not installed. Try: pip install sentence-transformers")
            self.model = CrossEncoder(self.model_name, device=self.device, max_length=self.max_length, trust_remote_code=True)
            self._predict = self._predict_ce

    # --- backends ---
    def _predict_ce(self, query: str, texts: List[str]) -> List[float]:
        pairs = [(query, t) for t in texts]
        scores = self.model.predict(pairs)  # higher is better
        return scores.tolist() if hasattr(scores, "tolist") else list(scores)

    def _predict_bge(self, query: str, texts: List[str]) -> List[float]:
        # BGE returns a list of scores; higher is better by default
        pairs = [[query, t] for t in texts]
        return self.model.compute_score(pairs)

    # --- API ---
    def rerank(self, query: str, hits: List[Dict], top_k: Optional[int] = None) -> List[Dict]:
        if not hits:
            return hits
        texts = [_hit_text(h) for h in hits]
        scores = self._predict(query, texts)
        # Attach and sort by score desc
        for h, s in zip(hits, scores):
            if isinstance(h, dict):
                h["rerank_score"] = float(s)
        order = sorted(range(len(hits)), key=lambda i: scores[i], reverse=True)
        top_k = top_k or len(hits)
        return [hits[i] for i in order[:top_k]]
