from __future__ import annotations
import json, os
from pathlib import Path
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from ..configs import settings

class FaissStore:
    def __init__(self, index_path: str, emb_path: str, corpus_jsonl_path: str, model_path: str):
        self.index_path = index_path
        self.emb_path = emb_path
        self.corpus_jsonl_path = corpus_jsonl_path
        self.model_path = model_path
        self.index = faiss.read_index(self.index_path)
        self.corpus = []
        with open(self.corpus_jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                self.corpus.append(json.loads(line))
        self.model = SentenceTransformer(self.model_path)
        try:
            with open(str(Path(index_path).with_name("index_meta.json")), "r", encoding="utf-8") as f:
                meta = json.load(f)
        except:
            meta = {}
        self.metric = meta.get("metric", "ip").lower()
        self.dim = meta.get("dimension", None)

    def _to_vec(self, text: str):
        return self.model.encode([text], normalize_embeddings=True).astype("float32")

    def search(self, query: str, k: int):
        q = self._to_vec(query)
        D, I = self.index.search(q, k)
        scores = []
        if self.metric in ("ip", "inner_product"):
            scores = D[0]
        else:
            scores = -D[0]
        out = []
        for rank, idx in enumerate(I[0]):
            if idx < 0 or idx >= len(self.corpus):
                continue
            item = self.corpus[idx]
            text = item.get("text") or item.get("passage") or item.get("content") or ""
            meta = {k: v for k, v in item.items() if k not in ("text", "passage", "content")}
            out.append({"id": int(idx), "score": float(scores[rank]), "text": text, "meta": meta})
        out.sort(key=lambda x: x["score"], reverse=True)
        return out

class Retriever:
    def __init__(self):
        self.store = FaissStore(
            settings.index_path,
            settings.emb_path,
            settings.corpus_jsonl_path,
            settings.embedding_model
        )

    def topk(self, query: str, k: int = 10):
        return self.store.search(query, k)

retriever_singleton = Retriever()
