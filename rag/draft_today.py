import argparse
from rag.retriever import Retriever
from rag.generator import generate
from pathlib import Path

TEMPLATE = """    あなたは日本語で短い技術エッセイを書くライターです。関西弁で、300〜600字。
次の素材（過去の知見）を1〜3個ほど引用しつつ、「今日の問い」「過去知見」「今日の一歩」の3段で構成してください。
なるべく曖昧表現を避け、読者が真似できる行動を1つ具体に書くこと。
---
テーマ: {topic}

素材:
{context}
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--topic", required=True)
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    r = Retriever(args.db, top_k=args.k)
    hits = r.query(args.topic)
    context = "\n\n".join([f"- {h['text'][:300]}" for h in hits])

    prompt = TEMPLATE.format(topic=args.topic, context=context)
    out = generate(prompt)

    Path("storage/logs").mkdir(parents=True, exist_ok=True)
    Path("storage/logs/last_draft.txt").write_text(out, encoding="utf-8")
    print(out)

if __name__ == "__main__":
    main()
