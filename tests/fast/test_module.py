import haybarn


class TestModule:
    def test_paramstyle(self):
        assert haybarn.paramstyle == "qmark"

    def test_threadsafety(self):
        assert haybarn.threadsafety == 1

    def test_apilevel(self):
        assert haybarn.apilevel == "2.0"
