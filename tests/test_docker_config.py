"""Regression test: docker/config.py must expose APRS_* keys read via _get_from_config in aprs.py.

This guards against the Docker config surface drifting out of sync with the
keys consumed by aprs_backend/aprs.py.
"""
import importlib
import sys
import os
from pathlib import Path


def test_docker_config_exposes_aprs_login_read_timeout():
    """docker/config.py must define APRS_LOGIN_READ_TIMEOUT so that
    _get_from_config("APRS_LOGIN_READ_TIMEOUT", ...) in aprs.py resolves
    the env var instead of silently falling through to the default."""

    # Load docker/config.py as a module.  It calls sys.exit(1) when
    # APRS_CALLSIGN / APRS_PASSWORD are missing, so stub those env vars.
    env_backup = {}
    for var in ("APRS_CALLSIGN", "APRS_PASSWORD"):
        env_backup[var] = os.environ.get(var)
        os.environ[var] = os.environ.get(var, "TEST")

    try:
        config_path = Path(__file__).resolve().parent.parent / "docker" / "config.py"
        spec = importlib.util.spec_from_file_location("docker_config", config_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert hasattr(mod, "APRS_LOGIN_READ_TIMEOUT"), (
            "docker/config.py must expose APRS_LOGIN_READ_TIMEOUT"
        )
        assert mod.APRS_LOGIN_READ_TIMEOUT == "10.0", (
            "APRS_LOGIN_READ_TIMEOUT default must be '10.0' to match aprs.py"
        )
    finally:
        for var, old_val in env_backup.items():
            if old_val is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = old_val
        sys.modules.pop("docker_config", None)


def test_docker_config_aprs_login_read_timeout_honors_env():
    """When APRS_LOGIN_READ_TIMEOUT is set in the environment, docker/config.py
    must reflect that value (not the default)."""

    env_backup = {}
    for var in ("APRS_CALLSIGN", "APRS_PASSWORD", "APRS_LOGIN_READ_TIMEOUT"):
        env_backup[var] = os.environ.get(var)
        os.environ[var] = os.environ.get(var, "TEST" if var != "APRS_LOGIN_READ_TIMEOUT" else "20.0")

    try:
        config_path = Path(__file__).resolve().parent.parent / "docker" / "config.py"
        spec = importlib.util.spec_from_file_location("docker_config_env", config_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert mod.APRS_LOGIN_READ_TIMEOUT == "20.0", (
            "docker/config.py must honor the APRS_LOGIN_READ_TIMEOUT env var"
        )
    finally:
        for var, old_val in env_backup.items():
            if old_val is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = old_val
        sys.modules.pop("docker_config_env", None)
