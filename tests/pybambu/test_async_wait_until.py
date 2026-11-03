import asyncio
import unittest

from pybambu.utils import async_wait_until


class TestAsyncWaitUntil(unittest.TestCase):
    def test_returns_true_once_the_condition_holds(self):
        calls = []

        def condition():
            calls.append(1)
            return len(calls) >= 3

        self.assertTrue(asyncio.run(async_wait_until(condition, timeout=2, interval=0.001)))

    def test_returns_false_on_timeout(self):
        self.assertFalse(asyncio.run(async_wait_until(lambda: False, timeout=0.01, interval=0.001)))
