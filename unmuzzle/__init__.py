"""Unmuzzle: censorship-resistant distribution for open-weight models."""

try:
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("unmuzzle")
except Exception:  # not installed (running from a bare source tree)
    __version__ = "0.0.0+dev"
