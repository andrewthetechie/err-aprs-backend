"""Nox sessions."""

import nox

package = "aprs_backend"
python_versions = [
    "3.13",
]
nox.needs_version = ">= 2021.6.6"
nox.options.sessions = (
    "pre-commit",
    "bandit",
    "tests",
)
# uv manages the virtual environment and Python version, so nox runs
# sessions against the current environment and delegates to `uv run`.
nox.options.force_venv_backend = "none"


@nox.session(name="pre-commit")
def precommit(session: nox.Session) -> None:
    """Lint using pre-commit."""
    args = session.posargs or ["run", "--all-files", "--show-diff-on-failure"]
    session.run("uv", "run", "pre-commit", *args)


@nox.session
def bandit(session: nox.Session) -> None:
    """Run bandit security tests"""
    args = session.posargs or ["-r", "./aprs_backend"]
    session.run("uv", "run", "bandit", *args)


@nox.session
def tests(session: nox.Session) -> None:
    """Run the test suite."""
    session.run("uv", "run", "pytest", *session.posargs)
