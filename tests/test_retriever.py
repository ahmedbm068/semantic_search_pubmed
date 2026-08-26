"""Unit tests for retrieval logic (no model or FAISS index required)."""
import numpy as np
import pytest

from src.app.services.lexical import BM25Index, tokenize
from src.app.services.retriever import SearchService, _norm_model_id

DOCS = [
    "Metformin is a first line therapy for type 2 diabetes mellitus.",
    "Inhaled corticosteroids reduce asthma exacerbations in adults.",
    "Statins lower LDL cholesterol and cardiovascular risk.",
    "Insulin glargine provides basal glycemic control in diabetes.",
]


class TestTokenizer:
    def test_lowercases_and_splits_on_non_alphanumeric(self):
        assert tokenize("Type-2 Diabetes (mellitus)!") == ["type", "2", "diabetes", "mellitus"]

    def test_empty_string_yields_no_tokens(self):
        assert tokenize("") == []


class TestBM25:
    def test_ranks_lexically_matching_document_first(self):
        idx = BM25Index().fit(DOCS)
        ids, scores = idx.search("metformin diabetes therapy", k=4)
        assert ids[0] == 0
        assert scores[0] > 0

    def test_out_of_vocabulary_query_returns_empty(self):
        idx = BM25Index().fit(DOCS)
        ids, scores = idx.search("zzzznonexistent", k=4)
        assert ids.size == 0 and scores.size == 0

    def test_k_larger_than_corpus_is_clamped(self):
        idx = BM25Index().fit(DOCS)
        ids, _ = idx.search("diabetes", k=100)
        assert len(ids) == len(DOCS)

    def test_scores_are_descending(self):
        idx = BM25Index().fit(DOCS)
        _, scores = idx.search("diabetes insulin control", k=4)
        assert list(scores) == sorted(scores, reverse=True)

    def test_rarer_term_outranks_common_one(self):
        # "diabetes" appears in 2 docs, "glargine" in 1 -> higher IDF.
        idx = BM25Index().fit(DOCS)
        ids, _ = idx.search("glargine", k=1)
        assert ids[0] == 3

    def test_search_before_fit_raises(self):
        with pytest.raises(RuntimeError):
            BM25Index().search("anything", k=1)


class TestScoreNormalisation:
    def test_maps_range_to_unit_interval(self):
        out = SearchService._minmax(np.array([2.0, 4.0, 6.0], dtype="float32"))
        assert out.min() == pytest.approx(0.0)
        assert out.max() == pytest.approx(1.0)

    def test_constant_input_does_not_divide_by_zero(self):
        out = SearchService._minmax(np.array([3.0, 3.0, 3.0], dtype="float32"))
        assert np.all(out == 1.0)

    def test_empty_input_is_passed_through(self):
        assert SearchService._minmax(np.array([], dtype="float32")).size == 0


class TestModelIdentityCheck:
    @pytest.mark.parametrize(
        "a,b",
        [
            ("models/biomed-miniLM", "models\\biomed-miniLM"),
            ("/abs/path/models/biomed-miniLM", "models/biomed-miniLM"),
            ("models/BIOMED-MINILM", "models/biomed-minilm"),
        ],
    )
    def test_equivalent_identifiers_match(self, a, b):
        assert _norm_model_id(a) == _norm_model_id(b)

    def test_different_models_do_not_match(self):
        assert _norm_model_id("models/biomed-miniLM") != _norm_model_id("all-MiniLM-L6-v2")

    def test_missing_value_is_empty(self):
        assert _norm_model_id(None) == ""


class TestHybridSearch:
    def test_blank_query_returns_nothing(self, fake_index):
        assert fake_index.search("   ", k=5) == []

    def test_returns_at_most_k(self, fake_index):
        assert len(fake_index.search("diabetes", k=2)) <= 2

    def test_hybrid_surfaces_lexical_only_match(self, fake_index):
        # The stub dense index always ranks doc 0 first, so a doc that only BM25
        # finds must be coming from the lexical half of the fusion.
        hits = fake_index.search("corticosteroids asthma", k=4, hybrid=True)
        assert any(h["id"] == 1 for h in hits)

    def test_min_score_filters_results(self, fake_index):
        all_hits = fake_index.search("diabetes", k=4, hybrid=True)
        assert all_hits
        cutoff = max(h["score"] for h in all_hits)
        filtered = fake_index.search("diabetes", k=4, hybrid=True, min_score=cutoff)
        assert all(h["score"] >= cutoff for h in filtered)

    def test_results_are_sorted_by_score(self, fake_index):
        hits = fake_index.search("diabetes insulin", k=4, hybrid=True)
        scores = [h["score"] for h in hits]
        assert scores == sorted(scores, reverse=True)

    def test_hit_shape_is_stable(self, fake_index):
        hit = fake_index.search("diabetes", k=1)[0]
        assert set(hit) == {"id", "score", "text", "meta"}
        assert isinstance(hit["id"], int)
        assert isinstance(hit["score"], float)
