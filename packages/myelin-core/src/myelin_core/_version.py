"""The single source of the product version (CHANGELOG.md heads with the same number).

Every other place that states a version — the four `pyproject.toml` files, the Hub web
`package.json`, `uv.lock`, the README status line — is a copy written by
`scripts/sync_version.py` and checked by `tests/test_version.py`. Change the version here, run
the script, add the CHANGELOG entry.
"""

__version__ = "1.4.0"
