import logging

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


def test_misspelled_fallback_applied():
    """Misspelled value is applied as fallback when the correct key is unset."""
    bot_config = StubConfig(APRS_MAX_AGE_CACHED_PACETS_SECONDS="1800")
    assert APRSBackend._resolve_max_age_seconds(bot_config) == 1800


def test_default_when_neither_set():
    """Default 3600 is used when neither key is set."""
    bot_config = StubConfig()
    assert APRSBackend._resolve_max_age_seconds(bot_config) == 3600


def test_deprecation_warning_on_misspelled_fallback(caplog):
    """Deprecation warning is emitted when the misspelled key is used."""
    logger = logging.getLogger("aprs_backend.aprs")
    with caplog.at_level(logging.WARNING, logger=logger.name):
        bot_config = StubConfig(APRS_MAX_AGE_CACHED_PACETS_SECONDS="1800")
        result = APRSBackend._resolve_max_age_seconds(bot_config)
    assert result == 1800
    assert "APRS_MAX_AGE_CACHED_PACETS_SECONDS" in caplog.text
    assert "APRS_MAX_AGE_CACHED_PACKETS_SECONDS" in caplog.text


def test_no_deprecation_warning_with_correct_key(caplog):
    """No deprecation warning when the correctly-spelled key is set."""
    logger = logging.getLogger("aprs_backend.aprs")
    with caplog.at_level(logging.WARNING, logger=logger.name):
        bot_config = StubConfig(APRS_MAX_AGE_CACHED_PACKETS_SECONDS="7200")
        result = APRSBackend._resolve_max_age_seconds(bot_config)
    assert result == 7200
    assert "APRS_MAX_AGE_CACHED_PACETS_SECONDS" not in caplog.text


def test_no_deprecation_warning_with_default(caplog):
    """No deprecation warning when neither key is set (default 3600)."""
    logger = logging.getLogger("aprs_backend.aprs")
    with caplog.at_level(logging.WARNING, logger=logger.name):
        bot_config = StubConfig()
        result = APRSBackend._resolve_max_age_seconds(bot_config)
    assert result == 3600
    assert "APRS_MAX_AGE_CACHED_PACETS_SECONDS" not in caplog.text


def test_correct_spelling_wins_when_both_set():
    """Correctly-spelled key wins when both correct and misspelled keys are present."""
    bot_config = StubConfig(
        APRS_MAX_AGE_CACHED_PACKETS_SECONDS="7200",
        APRS_MAX_AGE_CACHED_PACETS_SECONDS="1800",
    )
    assert APRSBackend._resolve_max_age_seconds(bot_config) == 7200
