from aprs_backend.aprs import APRSBackend


class StubConfig:
    """Minimal config stub exposing only the attributes needed for max_age tests."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_correct_spelling_applied():
    """Correct-spelling value is applied when set."""
    bot_config = StubConfig(APRS_MAX_AGE_CACHED_PACKETS_SECONDS="7200")
    assert APRSBackend._resolve_max_age_seconds(bot_config) == 7200


def test_default_when_not_set():
    """Default 3600 is used when the key is not set."""
    bot_config = StubConfig()
    assert APRSBackend._resolve_max_age_seconds(bot_config) == 3600
