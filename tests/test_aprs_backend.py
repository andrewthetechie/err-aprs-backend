from unittest.mock import MagicMock
from types import SimpleNamespace
import pytest

from aprs_backend.clients.beacon import BeaconConfig
from aprs_backend.aprs import APRSBackend


class _MinimalAPRSBackend:
    """Minimal stub of APRSBackend that only provides _get_beacon_config's dependencies."""

    def __init__(self, bot_config: SimpleNamespace, callsign: str = "TEST-1"):
        self.bot_config = bot_config
        self.callsign = callsign

    # Bind the real _get_beacon_config and _get_from_config from APRSBackend
    _get_beacon_config = APRSBackend._get_beacon_config
    _get_from_config = APRSBackend._get_from_config


@pytest.fixture
def valid_bot_config():
    """Bot config with all beacon fields set and enabled."""
    return SimpleNamespace(
        APRS_BEACON_ENABLE="true",
        APRS_BEACON_LATITUDE="40.0",
        APRS_BEACON_LONGITUDE="-74.0",
        APRS_BEACON_SYMBOL="l",
        APRS_BEACON_SYMBOL_TABLE="/",
    )


@pytest.fixture
def backend(valid_bot_config):
    return _MinimalAPRSBackend(valid_bot_config, callsign="TEST-1")


def test_beacon_enabled_returns_config(backend):
    """APRS_BEACON_ENABLE='true' with valid fields returns a BeaconConfig."""
    result = backend._get_beacon_config()
    assert result is not None
    assert isinstance(result, BeaconConfig)
    assert result.from_call == "TEST-1"
    assert result.latitude == 40.0
    assert result.longitude == -74.0


def test_beacon_disabled_returns_none():
    """APRS_BEACON_ENABLE='false' returns None."""
    config = SimpleNamespace(APRS_BEACON_ENABLE="false")
    backend = _MinimalAPRSBackend(config, callsign="TEST-1")
    assert backend._get_beacon_config() is None


def test_beacon_unset_returns_none():
    """APRS_BEACON_ENABLE unset (defaults to 'false') returns None."""
    config = SimpleNamespace()
    backend = _MinimalAPRSBackend(config, callsign="TEST-1")
    assert backend._get_beacon_config() is None


def test_beacon_enabled_missing_latitude_returns_none():
    """APRS_BEACON_ENABLE='true' but latitude missing returns None."""
    config = SimpleNamespace(
        APRS_BEACON_ENABLE="true",
        APRS_BEACON_LONGITUDE="-74.0",
        APRS_BEACON_SYMBOL="l",
        APRS_BEACON_SYMBOL_TABLE="/",
    )
    backend = _MinimalAPRSBackend(config, callsign="TEST-1")
    assert backend._get_beacon_config() is None
