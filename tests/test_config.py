from modules import config


def test_hardening_defaults_exist():
    assert config.RATE_PER_MIN == 20
    assert config.DELAY_RANGE == (1.0, 3.0)
    assert config.MAX_REQUESTS == 800
    assert config.MAX_EXPANSIONS_PER_LAYER == 15
    assert config.BACKOFF_CAP == 300
