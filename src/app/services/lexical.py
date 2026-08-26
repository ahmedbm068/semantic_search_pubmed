"""Sparse BM25 index used as the lexical half of hybrid retrieval.

Implemented directly on scipy sparse rather than pulling in `rank_bm25`, which
scores documents in a Python loop. Here the per-(term, doc) BM25 weights are
precomputed once, so a query is a single sparse mat-vec.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import CountVectorizer

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Index:
    """Okapi BM25 over a fixed corpus.

    Weights are baked into a CSR matrix at build time:

        w[d, t] = idf[t] * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * len_d / avgdl))

    so ``scores = W @ q`` where ``q`` counts query-term occurrences.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.vectorizer: CountVectorizer | None = None
        self.weights: sp.csr_matrix | None = None

    def fit(self, documents: Sequence[str]) -> BM25Index:
        self.vectorizer = CountVectorizer(
            tokenizer=tokenize, lowercase=True, token_pattern=None, dtype=np.float32
        )
        tf = self.vectorizer.fit_transform(documents).tocsr()  # (n_docs, vocab)
        n_docs = tf.shape[0]

        doc_len = np.asarray(tf.sum(axis=1)).ravel()
        avgdl = float(doc_len.mean()) if n_docs else 0.0

        # df per term = number of docs with a non-zero count
        df = np.asarray((tf > 0).sum(axis=0)).ravel()
        idf = np.log(1.0 + (n_docs - df + 0.5) / (df + 0.5)).astype(np.float32)

        # Operate on the CSR data array directly; indptr gives each row's slice,
        # so the length normaliser can be broadcast per document.
        tf_data = tf.data
        rows = np.repeat(np.arange(n_docs), np.diff(tf.indptr))
        denom_norm = (
            self.k1 * (1.0 - self.b + self.b * doc_len[rows] / (avgdl or 1.0))
        ).astype(np.float32)

        weighted = tf_data * (self.k1 + 1.0) / (tf_data + denom_norm)
        weighted = weighted * idf[tf.indices]

        self.weights = sp.csr_matrix(
            (weighted.astype(np.float32), tf.indices, tf.indptr), shape=tf.shape
        )
        return self

    def search(self, query: str, k: int) -> tuple[np.ndarray, np.ndarray]:
        """Return (indices, scores) for the top-k documents, best first."""
        if self.weights is None or self.vectorizer is None:
            raise RuntimeError("BM25Index.fit() must be called before search()")

        q = self.vectorizer.transform([query])  # (1, vocab), raw counts
        if q.nnz == 0:  # no query term is in the vocabulary
            return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float32)

        scores = np.asarray((self.weights @ q.T).todense()).ravel()

        k = min(k, scores.shape[0])
        if k <= 0:
            return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float32)

        # argpartition avoids a full sort of 17.5k scores for a top-10 request.
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return top.astype(np.int64), scores[top].astype(np.float32)

    @property
    def size(self) -> int:
        return 0 if self.weights is None else self.weights.shape[0]
