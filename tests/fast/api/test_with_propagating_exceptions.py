import pytest

import haybarn


class TestWithPropagatingExceptions:
    def test_with(self):
        # Should propagate exception raised in the 'with haybarn.connect() ..'
        with (
            pytest.raises(haybarn.CatalogException, match="Table with name invalid does not exist"),
            haybarn.connect() as con,
        ):
            con.execute("SELECT * FROM invalid")

        # Does not raise an exception
        with haybarn.connect() as con:
            con.execute("select 1")
