# Contributor Guide

Thank you for your interest in improving this project.
This project is open-source under the [MIT license](https://opensource.org/licenses/MIT) and
welcomes contributions in the form of bug reports, feature requests, and pull requests.

Here is a list of important resources for contributors:

- [Source Code](https://github.com/andrewthetechie/err-aprs-backend)
- [Issue Tracker](https://github.com/andrewthetechie/err-aprs-backend/issues)
- [Code of Conduct](CODE_OF_CONDUCT.md)

---

## How to report a bug

Report bugs on the [Issue Tracker](https://github.com/andrewthetechie/err-aprs-backend/issues).

When filing an issue, make sure to answer these questions:

- Which operating system and Python version are you using?
- Which version of this project are you using?
- What did you do?
- What did you expect to see?
- What did you see instead?

The best way to get your bug fixed is to provide a test case,
and/or steps to reproduce the issue.

---

## How to request a feature

Request features on the [Issue Tracker](https://github.com/andrewthetechie/err-aprs-backend/issues).

---

## Development setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and
[Nox](https://nox.thea.codes/) to run the checks (tests, linting, and security scans).

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (which manages Python 3.13 and the virtual environment)

### First-time setup

```console
$ uv sync
```

This creates a `.venv` with the project installed in editable mode, along with all
development dependencies (pytest, pre-commit, bandit, nox, etc.).

### Running checks

Run the full suite of checks (pre-commit, bandit, tests):

```console
$ nox
```

Or run individual sessions:

```console
$ nox -s pre-commit   # lint and format checks
$ nox -s bandit       # security scan of aprs_backend
$ nox -s tests        # pytest suite with coverage
```

You can also invoke the tools directly through uv:

```console
$ uv run pytest
$ uv run pre-commit run --all-files
$ uv run bandit -r ./aprs_backend
```

---
