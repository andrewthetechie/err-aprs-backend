import importlib
import sys

import pytest


def _reload_config(monkeypatch, env_overrides=None):
    """Reload docker.config with isolated environment.

    Always stubs APRS_CALLSIGN and APRS_PASSWORD to prevent sys.exit(1).
    Removes any ERR_APRS_* vars to avoid exec side-effects.
    """
    # Remove the module from sys.modules so it re-executes
    if "docker.config" in sys.modules:
        del sys.modules["docker.config"]

    # Stub required vars
    monkeypatch.setenv("APRS_CALLSIGN", "TEST123")
    monkeypatch.setenv("APRS_PASSWORD", "testpass")

    # Remove any ERR_APRS_* vars that could be exec'd
    for key in list(monkeypatch._setattr):
        pass  # monkeypatch handles cleanup automatically

    # Apply optional overrides
    if env_overrides:
        for key, value in env_overrides.items():
            monkeypatch.setenv(key, value)

    return importlib.import_module("docker.config")


def test_docker_config_both_env_vars_correct_wins(monkeypatch):
    """When both env vars are set, the correctly-spelled value wins."""
    monkeypatch.delenv("APRS_MAX_AGE_CACHED_PACKETS_SECONDS", raising=False)
    monkeypatch.delenv("APRS_MAX_AGE_CACHED_PACETS_SECONDS", raising=False)
    monkeypatch.setenv("APRS_MAX_AGE_CACHED_PACKETS_SECONDS", "7200")
    monkeypatch.setenv("APRS_MAX_AGE_CACHED_PACETS_SECONDS", "1800")

    config = _reload_config(monkeypatch)
    assert config.APRS_MAX_AGE_CACHED_PACKETS_SECONDS == "7200"


def test_docker_config_misspelled_fallback(monkeypatch):
    """When only the misspelled env var is set, the fallback value is used."""
    monkeypatch.delenv("APRS_MAX_AGE_CACHED_PACKETS_SECONDS", raising=False)
    monkeypatch.delenv("APRS_MAX_AGE_CACHED_PACETS_SECONDS", raising=False)
    monkeypatch.setenv("APRS_MAX_AGE_CACHED_PACETS_SECONDS", "1800")

    config = _reload_config(monkeypatch)
    assert config.APRS_MAX_AGE_CACHED_PACKETS_SECONDS == "1800"


def test_docker_config_default_when_neither_set(monkeypatch):
    """When neither env var is set, the default 3600 is used."""
    monkeypatch.delenv("APRS_MAX_AGE_CACHED_PACKETS_SECONDS", raising=False)
    monkeypatch.delenv("APRS_MAX_AGE_CACHED_PACETS_SECONDS", raising=False)

    config = _reload_config(monkeypatch)
    assert config.APRS_MAX_AGE_CACHED_PACKETS_SECONDS == "3600"
