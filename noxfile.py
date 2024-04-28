"""Nox sessions."""

import os
import shlex
import sys
from pathlib import Path
from textwrap import dedent

import nox
import toml

try:
    from nox_poetry import Session
    from nox_poetry import session
except ImportError:
    message = f"""\
    Nox failed to import the 'nox-poetry' package.

    Please install it using the following command:

    {sys.executable} -m pip install nox-poetry"""
    raise SystemExit(dedent(message)) from None


package = "aprs_backend"
python_versions = [
    "3.11",
]
nox.needs_version = ">= 2021.6.6"
nox.options.sessions = (
    "pre-commit",
    "bandit",
    "tests",
)
mypy_type_packages = ()
pyproject = toml.load("pyproject.toml")
test_requirements = list(pyproject["tool"]["poetry"]["group"]["dev"]["dependencies"].keys())
errbot_version = pyproject["tool"]["errbot"]["backend_plugins"]["supported_errbot_version"]
# test_requirements.append(f"errbot{errbot_version}")


def activate_virtualenv_in_precommit_hooks(session: Session) -> None:
    """Activate virtualenv in hooks installed by pre-commit.

    This function patches git hooks installed by pre-commit to activate the
    session's virtual environment. This allows pre-commit to locate hooks in
    that environment when invoked from git.

    Args:
        session: The Session object.
    """
    assert session.bin is not None  # noqa: S101

    # Only patch hooks containing a reference to this session's bindir. Support
    # quoting rules for Python and bash, but strip the outermost quotes so we
    # can detect paths within the bindir, like <bindir>/python.
    bindirs = [
        bindir[1:-1] if bindir[0] in "'\"" else bindir for bindir in (repr(session.bin), shlex.quote(session.bin))
    ]

    virtualenv = session.env.get("VIRTUAL_ENV")
    if virtualenv is None:
        return

    headers = {
        # pre-commit < 2.16.0
        "python": f"""\
            import os
            os.environ["VIRTUAL_ENV"] = {virtualenv!r}
            os.environ["PATH"] = os.pathsep.join((
                {session.bin!r},
                os.environ.get("PATH", ""),
            ))
            """,
        # pre-commit >= 2.16.0
        "bash": f"""\
            VIRTUAL_ENV={shlex.quote(virtualenv)}
            PATH={shlex.quote(session.bin)}"{os.pathsep}$PATH"
            """,
    }

    hookdir = Path(".git") / "hooks"
    if not hookdir.is_dir():
        return

    for hook in hookdir.iterdir():
        if hook.name.endswith(".sample") or not hook.is_file():
            continue

        if not hook.read_bytes().startswith(b"#!"):
            continue

        text = hook.read_text()

        if not any(Path("A") == Path("a") and bindir.lower() in text.lower() or bindir in text for bindir in bindirs):
            continue

        lines = text.splitlines()

        for executable, header in headers.items():
            if executable in lines[0].lower():
                lines.insert(1, dedent(header))
                hook.write_text("\n".join(lines))
                break


@session(name="pre-commit", python=python_versions[0])
def precommit(session: Session) -> None:
    """Lint using pre-commit."""
    args = session.posargs or ["run", "--all-files", "--show-diff-on-failure"]
    session.install(*test_requirements)
    session.install(".")
    # errbot has weird conflicts with setuptools versions? Doesn't affect code at runtime, only in testing
    # eventually would be good to get this managed by poetry
    session.run("poetry", "run", "pip", "install", f"errbot{errbot_version}")
    session.run("pre-commit", *args)
    if args and args[0] == "install":
        activate_virtualenv_in_precommit_hooks(session)


@session(python=python_versions[0])
def bandit(session: Session) -> None:
    """Run bandit security tests"""
    session.install("bandit")
    args = session.posargs or ["-r", "./aprs_backend"]
    session.run("bandit", *args)


@session(python=python_versions)
def tests(session: Session) -> None:
    """Run the test suite."""
    session.install(".")
    session.install(*test_requirements)
    # errbot has weird conflicts with setuptools versions? Doesn't affect code at runtime, only in testing
    # eventually would be good to get this managed by poetry
    session.run("poetry", "run", "pip", "install", f"errbot{errbot_version}")
    session.run("poetry", "run", "pytest", *session.posargs)
