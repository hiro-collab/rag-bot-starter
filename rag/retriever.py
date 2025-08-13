from typing import List, Dict, Any
import chromadb
from chromadb.api.types import Documents, EmbeddingFunction
from chromadb.utils import embedding_functions

# Simple retriever for the 'days_collection'
class Retriever:
    def __init__(self, db_path: str, top_k: int = 5):
        self.client = chromadb.PersistentClient(path=db_path)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="intfloat/multilingual-e5-large"
        )
        self.col = self.client.get_collection("days_collection", embedding_function=ef)
        self.top_k = top_k

    def query(self, text: str) -> List[Dict[str, Any]]:
        res = self.col.query(query_texts=[text], n_results=self.top_k)
        items = []
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            items.append({"text": doc, "metadata": meta, "distance": float(dist)})
        return items
