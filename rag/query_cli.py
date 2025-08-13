import argparse
from rag.retriever import Retriever

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="Chroma directory")
    ap.add_argument("--q", required=True, help="Query")
    args = ap.parse_args()

    r = Retriever(args.db, top_k=5)
    hits = r.query(args.q)
    for i, h in enumerate(hits, 1):
        print(f"--- Hit #{i} (distance={h['distance']:.4f}) ---")
        print(h["metadata"])
        print(h["text"][:500])
        print()

if __name__ == "__main__":
    main()
