"""
=========================================================
NTIS Replay Package Tests
Version : 1.0
Purpose :
    Basic smoke tests for the
    Historical Replay Engine.
=========================================================
"""

import unittest

from replay_cache import ReplayCache
from replay_context import ReplayContext
from replay_state import ReplayState
from replay_timer import ReplayTimer


class TestReplayCache(unittest.TestCase):

    def test_cache(self):

        cache = ReplayCache()

        cache.set("A", 100)

        self.assertTrue(cache.exists("A"))
        self.assertEqual(cache.get("A"), 100)


class TestReplayContext(unittest.TestCase):

    def test_context(self):

        ctx = ReplayContext()

        ctx.set("Symbol", "RELIANCE")

        self.assertEqual(
            ctx.get("Symbol"),
            "RELIANCE",
        )


class TestReplayState(unittest.TestCase):

    def test_state(self):

        state = ReplayState()

        self.assertTrue(state.is_idle())

        state.set(ReplayState.RUNNING)

        self.assertTrue(state.is_running())


class TestReplayTimer(unittest.TestCase):

    def test_timer(self):

        timer = ReplayTimer()

        timer.start()

        elapsed = timer.stop()

        self.assertGreaterEqual(elapsed, 0.0)


if __name__ == "__main__":

    unittest.main()