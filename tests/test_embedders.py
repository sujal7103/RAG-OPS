"""Tests for embedder wrappers."""

import sys
import types

import numpy as np
import pytest

from rag_ops import embedders


class FakeSentenceModel:
    def __init__(self):
        self.calls = []

    def encode(self, texts, show_progress_bar=False, normalize_embeddings=True):
        self.calls.append(list(texts))
        if len(texts) == 1:
            return np.array([[3.0, 4.0]], dtype=np.float32)
        return np.array([[3.0, 4.0], [1.0, 0.0]], dtype=np.float32)


def test_embed_minilm_normalizes_output(monkeypatch):
    fake_model = FakeSentenceModel()
    monkeypatch.setattr(embedders, "_get_st_model", lambda name: fake_model)

    result = embedders.embed_minilm(["hello", "world"])

    assert result.shape == (2, 2)
    assert np.allclose(np.linalg.norm(result, axis=1), [1.0, 1.0])


def test_embed_bge_prefixes_query_text(monkeypatch):
    fake_model = FakeSentenceModel()
    monkeypatch.setattr(embedders, "_get_st_model", lambda name: fake_model)

    embedders.embed_bge(["find docs"], is_query=True)

    assert fake_model.calls[0][0].startswith(
        "Represent this sentence for searching relevant passages:"
    )


def test_embed_openai_requires_api_key():
    with pytest.raises(ValueError):
        embedders.embed_openai(["hello"], api_key="")


def test_embed_openai_batches_and_normalizes(monkeypatch):
    class FakeEmbeddingResponse:
        def __init__(self, data):
            self.data = data

    class FakeEmbeddingsClient:
        def __init__(self):
            self.calls = []

        def create(self, input, model):
            self.calls.append((list(input), model))
            return FakeEmbeddingResponse(
                [types.SimpleNamespace(embedding=[3.0, 4.0]) for _ in input]
            )

    class FakeOpenAIClient:
        def __init__(self, api_key):
            self.api_key = api_key
            self.embeddings = FakeEmbeddingsClient()

    fake_openai_module = types.SimpleNamespace(OpenAI=FakeOpenAIClient)
    monkeypatch.setitem(sys.modules, "openai", fake_openai_module)

    result = embedders.embed_openai(["a"] * 101, api_key="sk-test")

    assert result.shape == (101, 2)
    assert np.allclose(np.linalg.norm(result, axis=1), np.ones(101))

