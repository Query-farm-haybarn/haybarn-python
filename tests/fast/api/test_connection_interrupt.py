import platform
import threading
import time

import pytest

import haybarn


class TestConnectionInterrupt:
    @pytest.mark.xfail(
        condition=platform.system() == "Emscripten",
        reason="threads not allowed on Emscripten",
    )
    def test_connection_interrupt(self):
        conn = haybarn.connect()

        def interrupt() -> None:
            # Wait for query to start running before interrupting
            time.sleep(0.1)
            conn.interrupt()

        thread = threading.Thread(target=interrupt)
        thread.start()
        with pytest.raises(haybarn.InterruptException):
            conn.execute("select count(*) from range(100000000000)").fetchall()
        thread.join()

    def test_interrupt_closed_connection(self):
        conn = haybarn.connect()
        conn.close()
        with pytest.raises(haybarn.ConnectionException):
            conn.interrupt()
