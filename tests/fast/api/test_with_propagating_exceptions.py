import pytest

import haybarn


class TestWithPropagatingExceptions:
    def test_with(self):
        # Should propagate exception raised in the 'with haybarn.connect() ..'
        with pytest.raises(haybarn.ParserException, match=r"syntax error at or near *"), haybarn.connect() as con:
            con.execute("invalid")

        # Does not raise an exception
        with haybarn.connect() as con:
            con.execute("select 1")
