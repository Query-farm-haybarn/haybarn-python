import re

import pandas as pd
import pytest

import haybarn

pa = pytest.importorskip("pyarrow")


def is_dunder_method(method_name: str) -> bool:
    if len(method_name) < 4:
        return False
    if method_name.startswith("_pybind11"):
        return True
    return method_name[:2] == "__" and method_name[:-3:-1] == "__"


@pytest.fixture(scope="session")
def tmp_database(tmp_path_factory):
    database = tmp_path_factory.mktemp("databases", numbered=True) / "tmp.duckdb"
    return database


# This file contains tests for DuckDBPyConnection methods,
# wrapped by the 'duckdb' module, to execute with the 'default_connection'
class TestDuckDBConnection:
    def test_append(self):
        haybarn.execute("Create table integers (i integer)")
        df_in = pd.DataFrame(
            {
                "numbers": [1, 2, 3, 4, 5],
            }
        )
        haybarn.append("integers", df_in)
        assert haybarn.execute("select count(*) from integers").fetchone()[0] == 5
        # cleanup
        haybarn.execute("drop table integers")

    def test_default_connection_from_connect(self):
        haybarn.sql("create or replace table connect_default_connect (i integer)")
        con = haybarn.connect(":default:")
        con.sql("select i from connect_default_connect")
        haybarn.sql("drop table connect_default_connect")
        with pytest.raises(haybarn.Error):
            con.sql("select i from connect_default_connect")

        # not allowed with additional options
        with pytest.raises(
            haybarn.InvalidInputException, match="Default connection fetching is only allowed without additional options"
        ):
            con = haybarn.connect(":default:", read_only=True)

    def test_arrow(self):
        pytest.importorskip("pyarrow")
        haybarn.execute("select [1,2,3]")
        haybarn.to_arrow_table()

    def test_begin_commit(self):
        haybarn.begin()
        haybarn.execute("create table tbl as select 1")
        haybarn.commit()
        haybarn.table("tbl")
        haybarn.execute("drop table tbl")

    def test_begin_rollback(self):
        haybarn.begin()
        haybarn.execute("create table tbl as select 1")
        haybarn.rollback()
        with pytest.raises(haybarn.CatalogException):
            # Table does not exist
            haybarn.table("tbl")

    def test_cursor(self):
        haybarn.execute("create table tbl as select 3")
        duckdb_cursor = haybarn.cursor()
        res = duckdb_cursor.table("tbl").fetchall()
        assert res == [(3,)]
        duckdb_cursor.execute("drop table tbl")
        with pytest.raises(haybarn.CatalogException):
            # 'tbl' no longer exists
            haybarn.table("tbl")

    def test_cursor_lifetime(self):
        con = haybarn.connect()

        def use_cursors() -> None:
            cursors = [con.cursor() for _ in range(10)]

            for cursor in cursors:
                cursor.close()

        use_cursors()
        con.close()

    def test_df(self):
        ref = [([1, 2, 3],)]
        haybarn.execute("select [1,2,3]")
        res_df = haybarn.fetch_df()  # noqa: F841
        res = haybarn.query("select * from res_df").fetchall()
        assert res == ref

    def test_duplicate(self):
        haybarn.execute("create table tbl as select 5")
        dup_conn = haybarn.duplicate()
        dup_conn.table("tbl").fetchall()
        haybarn.execute("drop table tbl")
        with pytest.raises(haybarn.CatalogException):
            dup_conn.table("tbl").fetchall()

    def test_readonly_properties(self):
        haybarn.execute("select 42")
        description = haybarn.description()
        rowcount = haybarn.rowcount()
        assert description == [("42", "INTEGER", None, None, None, None, None)]
        assert rowcount == -1

    def test_execute(self):
        assert haybarn.execute("select [4,2]").fetchall() == [([4, 2],)]

    def test_executemany(self):
        # executemany does not keep an open result set
        # TODO: shouldn't we also have a version that executes a query multiple times with  # noqa: TD002, TD003
        #   different parameters, returning all of the results?
        haybarn.execute("create table tbl (i integer, j varchar)")
        haybarn.executemany("insert into tbl VALUES (?, ?)", [(5, "test"), (2, "duck"), (42, "quack")])
        res = haybarn.table("tbl").fetchall()
        assert res == [(5, "test"), (2, "duck"), (42, "quack")]
        haybarn.execute("drop table tbl")

    def test_pystatement(self):
        with pytest.raises(haybarn.ParserException, match="seledct"):
            statements = haybarn.extract_statements("seledct 42; select 21")

        statements = haybarn.extract_statements("select $1; select 21")
        assert len(statements) == 2
        assert statements[0].query == "select $1"
        assert statements[0].type == haybarn.StatementType.SELECT
        assert statements[0].named_parameters == set("1")
        assert statements[0].expected_result_type == [haybarn.ExpectedResultType.QUERY_RESULT]

        assert statements[1].query == " select 21"
        assert statements[1].type == haybarn.StatementType.SELECT
        assert statements[1].named_parameters == set()

        with pytest.raises(
            haybarn.InvalidInputException,
            match="Please provide either a DuckDBPyStatement or a string representing the query",
        ):
            haybarn.query(statements)

        with pytest.raises(haybarn.BinderException, match="This type of statement can't be prepared!"):
            haybarn.query(statements[0])

        assert haybarn.query(statements[1]).fetchall() == [(21,)]
        assert haybarn.execute(statements[1]).fetchall() == [(21,)]

        with pytest.raises(
            haybarn.InvalidInputException,
            match="Values were not provided for the following prepared statement parameters: 1",
        ):
            haybarn.execute(statements[0])
        assert haybarn.execute(statements[0], {"1": 42}).fetchall() == [(42,)]

        haybarn.execute("create table tbl(a integer)")
        statements = haybarn.extract_statements("insert into tbl select $1")
        assert statements[0].expected_result_type == [
            haybarn.ExpectedResultType.CHANGED_ROWS,
            haybarn.ExpectedResultType.QUERY_RESULT,
        ]
        with pytest.raises(
            haybarn.InvalidInputException, match="executemany requires a non-empty list of parameter sets to be provided"
        ):
            haybarn.executemany(statements[0])
        haybarn.executemany(statements[0], [(21,), (22,), (23,)])
        assert haybarn.table("tbl").fetchall() == [(21,), (22,), (23,)]
        haybarn.execute("drop table tbl")

    def test_arrow_table(self):
        # Needed for 'arrow_table'
        pytest.importorskip("pyarrow")

        haybarn.execute("Create Table test (a integer)")

        for i in range(1024):
            haybarn.execute("Insert Into test values ('" + str(i) + "')")
            haybarn.execute("Insert Into test values ('" + str(i) + "')")
        haybarn.execute("Insert Into test values ('5000')")
        haybarn.execute("Insert Into test values ('6000')")
        sql = """
        SELECT  a, COUNT(*) AS repetitions
        FROM    test
        GROUP BY a
        """

        result_df = haybarn.execute(sql).df()

        arrow_table = haybarn.execute(sql).to_arrow_table()

        arrow_df = arrow_table.to_pandas()
        assert result_df["repetitions"].sum() == arrow_df["repetitions"].sum()
        haybarn.execute("drop table test")

    def test_fetch_df(self):
        ref = [([1, 2, 3],)]
        haybarn.execute("select [1,2,3]")
        res_df = haybarn.fetch_df()  # noqa: F841
        res = haybarn.query("select * from res_df").fetchall()
        assert res == ref

    def test_fetch_df_chunk(self):
        haybarn.execute("CREATE table t as select range a from range(3000);")
        query = haybarn.execute("SELECT a FROM t")
        cur_chunk = query.fetch_df_chunk()
        assert cur_chunk["a"][0] == 0
        assert len(cur_chunk) == 2048
        cur_chunk = query.fetch_df_chunk()
        assert cur_chunk["a"][0] == 2048
        assert len(cur_chunk) == 952
        haybarn.execute("DROP TABLE t")

    def test_fetch_record_batch(self):
        # Needed for 'arrow_table'
        pytest.importorskip("pyarrow")

        haybarn.execute("CREATE table t as select range a from range(3000);")
        haybarn.execute("SELECT a FROM t")
        record_batch_reader = haybarn.to_arrow_reader(1024)
        chunk = record_batch_reader.read_all()
        assert len(chunk) == 3000

    def test_fetchall(self):
        assert haybarn.execute("select [1,2,3]").fetchall() == [([1, 2, 3],)]

    def test_fetchdf(self):
        ref = [([1, 2, 3],)]
        haybarn.execute("select [1,2,3]")
        res_df = haybarn.fetchdf()  # noqa: F841
        res = haybarn.query("select * from res_df").fetchall()
        assert res == ref

    def test_fetchmany(self):
        assert haybarn.execute("select * from range(5)").fetchmany(2) == [(0,), (1,)]

    def test_fetchnumpy(self):
        numpy = pytest.importorskip("numpy")
        haybarn.execute("SELECT BLOB 'hello'")
        results = haybarn.fetchall()
        assert results[0][0] == b"hello"

        haybarn.execute("SELECT BLOB 'hello' AS a")
        results = haybarn.fetchnumpy()
        assert results["a"] == numpy.array([b"hello"], dtype=object)

    def test_fetchone(self):
        assert haybarn.execute("select * from range(5)").fetchone() == (0,)

    def test_from_arrow(self):
        assert haybarn.from_arrow is not None

    def test_from_csv_auto(self):
        assert haybarn.from_csv_auto is not None

    def test_from_df(self):
        assert haybarn.from_df is not None

    def test_from_parquet(self):
        assert haybarn.from_parquet is not None

    def test_from_query(self):
        assert haybarn.from_query is not None

    def test_get_table_names(self):
        assert haybarn.get_table_names is not None

    def test_install_extension(self):
        assert haybarn.install_extension is not None

    def test_load_extension(self):
        assert haybarn.load_extension is not None

    def test_query(self):
        assert haybarn.query("select 3").fetchall() == [(3,)]

    def test_register(self):
        assert haybarn.register is not None

    def test_register_relation(self):
        con = haybarn.connect()
        rel = con.sql("select [5,4,3]")
        con.register("relation", rel)

        con.sql("create table tbl as select * from relation")
        assert con.table("tbl").fetchall() == [([5, 4, 3],)]

    def test_unregister_problematic_behavior(self, duckdb_cursor):
        # We have a VIEW called 'vw' in the Catalog
        duckdb_cursor.execute("create temporary view vw as from range(100)")
        assert duckdb_cursor.execute("select * from vw").fetchone() == (0,)

        # Create a registered object called 'vw'
        arrow_result = duckdb_cursor.execute("select 42").to_arrow_table()
        with pytest.raises(haybarn.CatalogException, match='View with name "vw" already exists'):
            duckdb_cursor.register("vw", arrow_result)

        # Temporary views take precedence over registered objects
        assert duckdb_cursor.execute("select * from vw").fetchone() == (0,)

        # Decide that we're done with this registered object..
        duckdb_cursor.unregister("vw")

        # This should not have affected the existing view:
        assert duckdb_cursor.execute("select * from vw").fetchone() == (0,)

    def test_unregister_quoted_table_names(self, duckdb_cursor):
        """Test that unregister works for quoted tables."""
        rel = duckdb_cursor.sql("select 'test', 'data'")

        table_name = 'test with .s and "s and  s'
        duckdb_cursor.register(table_name, rel)
        duckdb_cursor.unregister(table_name)

        escaped_table_name = table_name.replace('"', '""')
        with pytest.raises(haybarn.CatalogException):
            duckdb_cursor.sql(f'select * from "{escaped_table_name}"')

    def test_unregister_with_scary_name(self, duckdb_cursor):
        """Test that unregister doesn't have side effects."""
        rel = duckdb_cursor.sql("select 'test', 'data'")

        scary_name = 'test";create table foo as select * from range(10);--'
        # make sure a view with the name "test" exists
        duckdb_cursor.register("test", rel)
        duckdb_cursor.register(scary_name, rel)
        # try to trick unregister (which uses DROP VIEW) to run another statement
        duckdb_cursor.unregister(scary_name)

        # hopefully that didn't happen
        with pytest.raises(haybarn.CatalogException):
            duckdb_cursor.sql("select * from foo")

        # verify the scary name table was properly unregistered
        escaped_scary_name = scary_name.replace('"', '""')
        with pytest.raises(haybarn.CatalogException):
            duckdb_cursor.sql(f'select * from "{escaped_scary_name}"')

    def test_relation_out_of_scope(self):
        def temporary_scope():
            # Create a connection, we will return this
            con = haybarn.connect()
            # Create a dataframe
            df = pd.DataFrame({"a": [1, 2, 3]})
            # The dataframe has to be registered as well
            # making sure it does not go out of scope
            con.register("df", df)
            rel = con.sql("select * from df")
            con.register("relation", rel)
            return con

        con = temporary_scope()
        res = con.sql("select * from relation").fetchall()
        print(res)

    def test_table(self):
        con = haybarn.connect()
        con.execute("create table tbl as select 1")
        assert con.table("tbl").fetchall() == [(1,)]

    def test_table_function(self):
        assert haybarn.table_function is not None

    def test_unregister(self):
        assert haybarn.unregister is not None

    def test_values(self):
        assert haybarn.values is not None

    def test_view(self):
        haybarn.execute("create view vw as select range(5)")
        assert haybarn.view("vw").fetchall() == [([0, 1, 2, 3, 4],)]
        haybarn.execute("drop view vw")

    def test_close(self):
        assert haybarn.close is not None

    def test_interrupt(self):
        assert haybarn.interrupt is not None

    def test_wrap_shadowing(self):
        import pandas as pd_local

        import haybarn

        df = pd_local.DataFrame({"a": [1, 2, 3]})  # noqa: F841
        res = haybarn.sql("from df").fetchall()
        assert res == [(1,), (2,), (3,)]

    def test_wrap_coverage(self):
        con = haybarn.default_connection

        # Skip all of the initial __xxxx__ methods
        connection_methods = dir(con)
        filtered_methods = [method for method in connection_methods if not is_dunder_method(method)]
        for method in filtered_methods:
            # Assert that every method of DuckDBPyConnection is wrapped by the 'duckdb' module
            assert method in dir(duckdb)

    def test_connect_with_path(self, tmp_database):
        import pathlib

        assert isinstance(tmp_database, pathlib.Path)
        con = haybarn.connect(tmp_database)
        assert con.sql("select 42").fetchall() == [(42,)]

        with pytest.raises(
            haybarn.InvalidInputException,
            match=re.escape("Please provide either a str or a pathlib.Path, not <class 'int'>"),
        ):
            con = haybarn.connect(5)

    def test_set_pandas_analyze_sample_size(self):
        con = haybarn.connect(":memory:named", config={"pandas_analyze_sample": 0})
        res = con.sql("select current_setting('pandas_analyze_sample')").fetchone()
        assert res == (0,)

        # Find the cached config
        con2 = haybarn.connect(":memory:named", config={"pandas_analyze_sample": 0})
        con2.execute("SET GLOBAL pandas_analyze_sample=2")

        # This change is reflected in 'con' because the instance was cached
        res = con.sql("select current_setting('pandas_analyze_sample')").fetchone()
        assert res == (2,)
