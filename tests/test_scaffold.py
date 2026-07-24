"""WP0.1 acceptance: the scaffold imports, the CLI resolves, and network is blocked.

These are intentionally minimal — later WPs replace/extend them. Their job is to
prove the tooling loop (uv → pytest → CI) is green on an empty-ish suite.
"""

from __future__ import annotations

import importlib
import socket

import pytest
from pytest_socket import SocketBlockedError
from typer.testing import CliRunner

import ah
from ah.cli import app


def test_package_imports_and_has_version() -> None:
    assert ah.__version__ == "0.1.0"


def test_core_package_importable() -> None:
    """Import the core package so coverage registers it (and to prove layout)."""
    for sub in ("core", "store", "compiler", "battery"):
        importlib.import_module(f"ah.{sub}")


def test_cli_version_flag() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == ah.__version__


# pytest-socket's SocketBlockedError emits a UserWarning during construction;
# with filterwarnings=error that would mask the exception we mean to assert on.
@pytest.mark.filterwarnings("ignore::UserWarning")
def test_network_is_blocked_in_tests() -> None:
    """pytest-socket must forbid opening sockets (no network in tests/CI)."""
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
