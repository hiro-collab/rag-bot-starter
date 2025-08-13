import argparse
import json
from pathlib import Path
import chromadb
from chromadb.utils import embedding_functions

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True, help="JSONL chunks file")
    ap.add_argument("--db", required=True, help="Chroma directory")
    args = ap.parse_args()

    db_dir = Path(args.db)
    db_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(db_dir))
    # Use multilingual-e5-large for Japanese stability
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="intfloat/multilingual-e5-large"
    )
    col = client.get_or_create_collection(
        name="days_collection",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    ids, texts, metas = [], [], []
    with open(args.chunks, "r", encoding="utf-8") as fr:
        for line in fr:
            obj = json.loads(line)
            meta = obj.get("metadata", {})
            # ✅ Make ID unique by including the relative path
            rid = f"{meta.get('path','')}-{obj['id']}"
            ids.append(rid)
            texts.append(obj["text"])
            metas.append(meta)

    # Upsert
    if ids:
        col.upsert(ids=ids, documents=texts, metadatas=metas)

    print(f"✅ Indexed {len(ids)} chunks into Chroma at {db_dir}")

if __name__ == "__main__":
    main()

