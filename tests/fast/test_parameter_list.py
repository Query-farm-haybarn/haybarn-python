import pytest

import haybarn
import pandas as pd


class TestParameterList:
    def test_bool(self, duckdb_cursor):
        conn = haybarn.connect()
        conn.execute("create table bool_table (a bool)")
        conn.execute("insert into bool_table values (TRUE)")
        res = conn.execute("select count(*) from bool_table where a =?", [True])
        assert res.fetchone()[0] == 1

    def test_exception(self, duckdb_cursor):
        conn = haybarn.connect()
        df_in = pd.DataFrame(
            {
                "numbers": [1, 2, 3, 4, 5],
            }
        )
        conn.execute("create table bool_table (a bool)")
        conn.execute("insert into bool_table values (TRUE)")
        with pytest.raises(haybarn.NotImplementedException, match="Unable to transform"):
            conn.execute("select count(*) from bool_table where a =?", [df_in])

    def test_explicit_nan_param(self):
        con = haybarn.default_connection()
        res = con.execute("select isnan(cast(? as double))", (float("nan"),))
        assert res.fetchone()[0]

    @pytest.mark.parametrize(
        ("param", "query"),
        [
            ([float("nan")], "select isnan(?[1])"),
            ({"a": float("nan")}, "select isnan(?.a)"),
            ({"key": ["k"], "value": [float("nan")]}, "select isnan(?['k'])"),
            ([[1.0, float("nan")]], "select isnan(?[1][2])"),
            ([{"a": [float("nan")]}], "select isnan(?[1].a[1])"),
        ],
    )
    def test_nested_nan_param(self, param, query):
        con = haybarn.connect()
        assert con.execute(query, [param]).fetchone() == (True,)

    @pytest.mark.parametrize(
        ("value", "query"),
        [
            (haybarn.Value(float("nan"), haybarn.sqltype("DOUBLE")), "select isnan(?)"),
            (haybarn.Value({"k": float("nan")}, haybarn.sqltype("MAP(VARCHAR, DOUBLE)")), "select isnan(?['k'])"),
            (haybarn.Value({"a": float("nan")}, haybarn.sqltype("STRUCT(a DOUBLE)")), "select isnan(?.a)"),
            (haybarn.Value([float("nan"), 1.0], haybarn.sqltype("DOUBLE[2]")), "select isnan(?[1])"),
            (haybarn.Value({float("nan"): 1}, haybarn.sqltype("MAP(DOUBLE, INTEGER)")), "select isnan(map_keys(?)[1])"),
            (
                haybarn.Value((float("nan"), [float("nan")]), haybarn.sqltype("STRUCT(a DOUBLE, b DOUBLE[])")),
                "select isnan(?.b[1])",
            ),
        ],
    )
    def test_nan_typed_value_param(self, value, query):
        con = haybarn.connect()
        assert con.execute(query, [value]).fetchone() == (True,)

    def test_nested_nan_typed_param(self):
        con = haybarn.connect()
        value = haybarn.Value((float("nan"), 1.0), haybarn.sqltype("STRUCT(a DOUBLE, b DOUBLE)"))
        assert con.execute("select isnan(?.a)", [value]).fetchone() == (True,)

    def test_string_parameter(self, duckdb_cursor):
        conn = haybarn.connect()
        conn.execute("create table orders (o_orderdate date)")
        conn.execute("insert into orders values (date '1992-01-01'), (date '1994-01-01')")
        conn.execute(
            """
            SELECT COUNT(*)
            FROM ORDERS
            WHERE O_ORDERDATE BETWEEN ? AND ?
            """,
            ["1994-01-01", "1996-01-01"],
        )
        res = conn.fetchall()
        assert res == [(1,)]
