"""Dense + lexical retrieval over the PubMed FAISS index.

Two things this module is deliberate about:

1. **Nothing loads at import time.** The previous version built the singleton at
   module scope, so importing the app pulled a 26MB index, a 32MB corpus and a
   transformer into memory before the server existed (~25s, paid by every test
   run too). Loading now happens on first use, behind a lock.

2. **The index and the query model must agree.** An index built with the
   fine-tuned biomed-miniLM but queried with base MiniLM returns confident
   nonsense rather than an error. We compare against the metadata written at
   build time and refuse to serve on a mismatch.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

import numpy as np

from src.app.core.config import settings
from src.app.services.lexical import BM25Index

logger = logging.getLogger("app.retriever")


class IndexUnavailable(RuntimeError):
    """The index could not be loaded or does not match the configured model."""


def _norm_model_id(value: str | None) -> str:
    """Compare model identifiers by their final path segment.

    Build metadata stores whatever was passed on the command line
    (models/biomed-miniLM); config may hold an absolute path. Comparing the
    basename keeps those equivalent.
    """
    if not value:
        return ""
    return Path(str(value).replace("\\", "/")).name.strip().lower()


class SearchService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded = False
        self._index = None
        self._model = None
        self._cross_encoder_instance = None
        self._bm25: BM25Index | None = None
        self._corpus: list[dict[str, Any]] = []
        self._meta: dict[str, Any] = {}

    # ---------------- loading ----------------

    def _read_meta(self, index_path: Path) -> dict[str, Any]:
        meta_path = index_path.with_name("index_meta.json")
        try:
            with open(meta_path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("No index_meta.json beside %s; skipping model check", index_path)
            return {}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read %s: %s", meta_path, exc)
            return {}

    def _load(self) -> None:
        import faiss  # imported lazily: heavy, and not needed to import the app
        from sentence_transformers import SentenceTransformer

        index_path = Path(settings.index_file)
        corpus_path = Path(settings.corpus_file)

        for path, what in ((index_path, "FAISS index"), (corpus_path, "corpus")):
            if not path.exists():
                raise IndexUnavailable(
                    f"{what} not found at {path}. Build it with: "
                    f"python -m src.app.index.build_index --input data/raw/corpus.txt"
                )

        self._meta = self._read_meta(index_path)

        built_with = _norm_model_id(self._meta.get("model_path"))
        configured = _norm_model_id(settings.model_dir)
        if built_with and configured and built_with != configured:
            raise IndexUnavailable(
                f"Index/model mismatch: index was built with {self._meta.get('model_path')!r} "
                f"but EMBEDDING_MODEL is {settings.embedding_model!r}. Querying an index with a "
                f"different model returns meaningless scores. Either set EMBEDDING_MODEL to the "
                f"build model, or rebuild the index."
            )

        self._index = faiss.read_index(str(index_path))

        self._corpus = []
        with open(corpus_path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    self._corpus.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed corpus line %d", line_no)

        if self._index.ntotal != len(self._corpus):
            raise IndexUnavailable(
                f"Index has {self._index.ntotal} vectors but corpus has "
                f"{len(self._corpus)} documents. They are out of sync; rebuild the index."
            )

        self._model = SentenceTransformer(settings.model_dir)

        model_dim = self._model.get_sentence_embedding_dimension()
        if model_dim != self._index.d:
            raise IndexUnavailable(
                f"Embedding dimension mismatch: model produces {model_dim}-d vectors, "
                f"index expects {self._index.d}-d. Rebuild the index."
            )

        if settings.hybrid_enabled:
            self._bm25 = BM25Index().fit([self._text_of(d) for d in self._corpus])

        self._loaded = True
        logger.info(
            "Retriever ready: %d docs, dim=%d, model=%s, hybrid=%s",
            len(self._corpus),
            self._index.d,
            settings.model_dir,
            settings.hybrid_enabled,
        )

    def ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if not self._loaded:  # re-check: another thread may have won the race
                self._load()

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ---------------- helpers ----------------

    @staticmethod
    def _text_of(item: dict[str, Any]) -> str:
        for key in ("text", "passage", "content", "body", "abstract"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return ""

    def _hit(self, idx: int, score: float) -> dict[str, Any]:
        item = self._corpus[idx]
        meta = {k: v for k, v in item.items() if k not in ("text", "passage", "content")}
        return {"id": int(idx), "score": float(score), "text": self._text_of(item), "meta": meta}

    @staticmethod
    def _minmax(values: np.ndarray) -> np.ndarray:
        """Scale to [0, 1]. Dense cosine and BM25 scores are not comparable raw."""
        if values.size == 0:
            return values
        lo, hi = float(values.min()), float(values.max())
        if hi - lo < 1e-9:
            return np.ones_like(values, dtype=np.float32)
        return ((values - lo) / (hi - lo)).astype(np.float32)

    def _dense(self, query: str, k: int):
        vec = self._model.encode(
            [query], normalize_embeddings=True, show_progress_bar=False
        ).astype("float32")
        scores, ids = self._index.search(vec, min(k, self._index.ntotal))
        ids, scores = ids[0], scores[0]
        keep = ids >= 0  # FAISS pads with -1 when fewer than k results exist
        return ids[keep], scores[keep]

    # ---------------- public API ----------------

    def search(
        self,
        query: str,
        k: int = 10,
        min_score: float = 0.0,
        hybrid: bool | None = None,
        rerank: bool | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_loaded()

        query = (query or "").strip()
        if not query:
            return []

        k = max(1, min(int(k), settings.max_top_k))
        use_hybrid = settings.hybrid_enabled if hybrid is None else hybrid
        use_rerank = settings.rerank_enabled if rerank is None else rerank

        if use_hybrid and self._bm25 is not None:
            hits = self._search_hybrid(query, k)
        else:
            ids, scores = self._dense(query, k)
            hits = [self._hit(i, s) for i, s in zip(ids, scores, strict=True)]

        if use_rerank and hits:
            hits = self._rerank(query, hits, k)

        hits = [h for h in hits if h["score"] >= min_score]
        return hits[:k]

    def _search_hybrid(self, query: str, k: int) -> list[dict[str, Any]]:
        """Convex combination of min-max normalised dense and BM25 scores.

        Both retrievers propose hybrid_candidates documents; a document found by
        only one side keeps 0 for the other, which is what makes the union
        (rather than the intersection) improve recall.
        """
        pool = max(settings.hybrid_candidates, k)
        alpha = settings.hybrid_alpha

        dense_ids, dense_scores = self._dense(query, pool)
        lex_ids, lex_scores = self._bm25.search(query, pool)

        dense_norm = self._minmax(dense_scores)
        lex_norm = self._minmax(lex_scores)

        combined: dict[int, float] = {}
        for i, s in zip(dense_ids, dense_norm, strict=True):
            combined[int(i)] = alpha * float(s)
        for i, s in zip(lex_ids, lex_norm, strict=True):
            combined[int(i)] = combined.get(int(i), 0.0) + (1.0 - alpha) * float(s)

        ranked = sorted(combined.items(), key=lambda kv: kv[1], reverse=True)
        return [self._hit(i, s) for i, s in ranked[: max(pool, k)]]

    def _rerank(self, query: str, hits: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
        """Re-score top candidates with a cross-encoder.

        The cross-encoder reads query and document jointly, so it is far more
        accurate than the bi-encoder but too slow to run over the whole corpus.
        A failure here degrades to the original ranking rather than 500ing.
        """
        try:
            encoder = self._cross_encoder()
        except Exception as exc:
            logger.warning("Reranker unavailable, returning base ranking: %s", exc)
            return hits

        candidates = hits[: max(settings.rerank_candidates, k)]
        pairs = [(query, h["text"]) for h in candidates]
        try:
            scores = encoder.predict(pairs, show_progress_bar=False)
        except Exception as exc:
            logger.warning("Reranking failed, returning base ranking: %s", exc)
            return hits

        for hit, score in zip(candidates, scores, strict=False):
            hit["meta"] = {**hit.get("meta", {}), "base_score": hit["score"]}
            hit["score"] = float(score)
        candidates.sort(key=lambda h: h["score"], reverse=True)
        return candidates

    def _cross_encoder(self):
        if self._cross_encoder_instance is None:
            from sentence_transformers import CrossEncoder

            self._cross_encoder_instance = CrossEncoder(settings.rerank_model)
        return self._cross_encoder_instance

    def stats(self) -> dict[str, Any]:
        return {
            "loaded": self._loaded,
            "documents": len(self._corpus),
            "dimension": getattr(self._index, "d", None),
            "model": settings.embedding_model,
            "index_built_with": self._meta.get("model_path"),
            "hybrid": settings.hybrid_enabled,
            "hybrid_alpha": settings.hybrid_alpha,
            "rerank": settings.rerank_enabled,
        }


search_service = SearchService()
