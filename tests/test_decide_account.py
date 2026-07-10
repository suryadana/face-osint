from modules.search import decide_account


def test_ranking_max_and_consensus_match():
    r = decide_account([0.40, None, 0.38, 0.10], threshold=0.35, consensus_min=2)
    assert abs(r["score"] - 0.40) < 1e-9
    assert r["matched"] == 2
    assert r["is_match"] is True


def test_single_hit_is_not_match_under_consensus():
    r = decide_account([0.50, 0.10, None], threshold=0.35, consensus_min=2)
    assert abs(r["score"] - 0.50) < 1e-9
    assert r["matched"] == 1
    assert r["is_match"] is False


def test_all_none_gives_none_score():
    r = decide_account([None, None], threshold=0.35, consensus_min=2)
    assert r == {"score": None, "matched": 0, "is_match": False}
