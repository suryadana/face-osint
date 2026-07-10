from modules import config
from modules.search import cap_expansions


def test_cap_expansions_limits_count():
    users = [f"u{i}" for i in range(50)]
    assert cap_expansions(users, 15) == users[:15]


def test_cap_expansions_none_disables():
    users = ["a", "b", "c"]
    assert cap_expansions(users, None) == users
