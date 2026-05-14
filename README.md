# Haybarn — Python client

**The Python client for [Haybarn](https://github.com/Query-farm-haybarn/haybarn), an independent derived distribution of DuckDB, powered by DuckDB.**

Published by Query Farm LLC.

> Haybarn is **not** affiliated with, sponsored by, or endorsed by the DuckDB
> Foundation or DuckDB Labs. DuckDB is a trademark of the DuckDB Foundation.
> See [NOTICE](NOTICE).

This package is a fork of the DuckDB Python client, rebranded as `haybarn`. The
public API is identical to DuckDB's.

## Installation

```bash
pip install haybarn
```

## Usage

```python
import haybarn

haybarn.sql("SELECT 42").show()
```

### Migrating from DuckDB

Because the API is identical, existing DuckDB code needs only a one-line change:

```python
import haybarn as duckdb   # the rest of your code is unchanged
```

For third-party code you cannot edit, there is an **opt-in** compatibility shim
that makes `import duckdb` resolve to Haybarn:

```python
import haybarn.compat   # registers haybarn as the `duckdb` module
import duckdb           # now this is Haybarn
```

The compiled extension module is renamed (`_haybarn`), so a `haybarn` wheel and
a genuine `duckdb` wheel can be installed side by side without conflict.

## Building from source

See [CLAUDE.md](CLAUDE.md) for the build workflow. In short:

```bash
uv sync --only-group build --no-install-project
uv sync --no-build-isolation -v --reinstall
```

The DuckDB engine is built from the `external/duckdb` submodule.

## License

MIT — the same license as DuckDB. The upstream license is preserved in
[LICENSE](LICENSE); see [NOTICE](NOTICE) for the list of Haybarn modifications
and trademark attribution.
