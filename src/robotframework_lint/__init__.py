"""Robocop rule pack for Robot Framework."""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("robotframework-lint-lsp")
except PackageNotFoundError:  # running from a source tree
    __version__ = "0+unknown"
