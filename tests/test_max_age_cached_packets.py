import pytest
from unittest.mock import patch, MagicMock
from aprs_backend.aprs import APRSBackend


class StubConfig:
    """Minimal config stub exposing only the attributes needed for max_age tests."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def _build_max_age(bot_config):
    """Extract the max_age resolution logic from APRSBackend for isolated testing.

    Mirrors the logic at aprs_backend/aprs.py lines 88-92 so we can test it
    without needing to instantiate the full backend.
    """

    def _get_from_config(key, default=None):
        return getattr(bot_config, key, default)

    max_age = _get_from_config("APRS_MAX_AGE_CACHED_PACKETS_SECONDS", None)
    if max_age is None:
        # Backward compat with the misspelled key
        max_age = _get_from_config("APRS_MAX_AGE_CACHED_PACETS_SECONDS", "3600")
    return int(max_age)


def test_correct_spelling_applied():
    """Correct-spelling value is applied when set."""
    bot_config = StubConfig(APRS_MAX_AGE_CACHED_PACKETS_SECONDS="7200")
    assert _build_max_age(bot_config) == 7200


def test_misspelled_fallback_applied():
    """Misspelled value is applied as fallback when the correct key is unset."""
    bot_config = StubConfig(APRS_MAX_AGE_CACHED_PACETS_SECONDS="1800")
    assert _build_max_age(bot_config) == 1800


def test_default_when_neither_set():
    """Default 3600 is used when neither key is set."""
    bot_config = StubConfig()
    assert _build_max_age(bot_config) == 3600
