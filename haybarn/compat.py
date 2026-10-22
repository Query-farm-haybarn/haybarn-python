"""Opt-in DuckDB compatibility shim for Haybarn.

Haybarn's package and import name is ``haybarn``. Because Haybarn's public API
is identical to DuckDB's, migrating existing code is usually just::

    import haybarn as duckdb

For third-party code you cannot edit, importing this module registers
``haybarn`` under the name ``duckdb`` in ``sys.modules``, so that a later
``import duckdb`` resolves to Haybarn::

    import haybarn.compat   # noqa: F401
    import duckdb           # now this is Haybarn

This is **opt-in** by design — importing it is an explicit choice. It will not
silently shadow a genuine ``duckdb`` package that has already been imported.
"""

import sys

import haybarn

_existing = sys.modules.get("duckdb")
if _existing is not None and _existing is not haybarn:
    raise ImportError(
        "haybarn.compat: a real 'duckdb' module is already imported; "
        "refusing to shadow it. Import haybarn.compat before any 'import duckdb'."
    )

sys.modules["duckdb"] = haybarn
