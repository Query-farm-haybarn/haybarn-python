import haybarn


class TestContextManager:
    def test_context_manager(self, duckdb_cursor):
        with haybarn.connect(database=":memory:", read_only=False) as con:
            assert con.execute("select 1").fetchall() == [(1,)]
