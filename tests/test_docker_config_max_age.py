import importlib
import os
import sys


def _reload_config(monkeypatch, env_overrides=None):
    """Reload docker.config with isolated environment.

    Always stubs APRS_CALLSIGN and APRS_PASSWORD to prevent sys.exit(1).
    Removes any ERR_APRS_* vars to avoid exec side-effects.
    """
    # Remove the module from sys.modules so it re-executes
    if "docker.config" in sys.modules:
        del sys.modules["docker.config"]

    # Remove any ERR_APRS_* vars that could be exec'd
    for k in [k for k in os.environ if k.startswith("ERR_APRS_")]:
        monkeypatch.delenv(k, raising=False)

    # Stub required vars
    monkeypatch.setenv("APRS_CALLSIGN", "TEST123")
    monkeypatch.setenv("APRS_PASSWORD", "testpass")

    # Apply optional overrides
    if env_overrides:
        for key, value in env_overrides.items():
            monkeypatch.setenv(key, value)

    return importlib.import_module("docker.config")


def test_docker_config_correct_spelling_applied(monkeypatch):
    """Correctly-spelled env var is used when set."""
    monkeypatch.delenv("APRS_MAX_AGE_CACHED_PACKETS_SECONDS", raising=False)
    monkeypatch.setenv("APRS_MAX_AGE_CACHED_PACKETS_SECONDS", "7200")

    config = _reload_config(monkeypatch)
    assert config.APRS_MAX_AGE_CACHED_PACKETS_SECONDS == "7200"


def test_docker_config_default_when_not_set(monkeypatch):
    """Default 3600 is used when the env var is not set."""
    monkeypatch.delenv("APRS_MAX_AGE_CACHED_PACKETS_SECONDS", raising=False)

    config = _reload_config(monkeypatch)
    assert config.APRS_MAX_AGE_CACHED_PACKETS_SECONDS == "3600"
