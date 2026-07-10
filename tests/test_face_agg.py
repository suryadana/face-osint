import numpy as np
from modules.face import max_similarity


def test_max_similarity_picks_best():
    ref = np.array([1.0, 0.0, 0.0])
    embs = [
        np.array([0.0, 1.0, 0.0]),   # cos 0.0
        np.array([1.0, 1.0, 0.0]),   # cos ~0.707
        np.array([2.0, 0.0, 0.0]),   # cos 1.0
    ]
    assert abs(max_similarity(embs, ref) - 1.0) < 1e-6


def test_max_similarity_empty_is_none():
    assert max_similarity([], np.array([1.0, 0.0])) is None
