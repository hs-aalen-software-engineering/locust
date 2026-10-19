from locust.util.cache import memoize

import unittest
from unittest import mock


class FakeClock:
    """Manually advanced stand-in for time.time()."""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestMemoize(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        patcher = mock.patch("locust.util.cache.time", side_effect=self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_counted(self, timeout, dynamic_timeout=False, runtime=0.0):
        """Return (memoized function, call list). Each real execution advances the clock by `runtime`."""
        calls = []

        @memoize(timeout, dynamic_timeout=dynamic_timeout)
        def func(*args, **kwargs):
            calls.append((args, kwargs))
            self.clock.advance(runtime)
            return f"result-{len(calls)}"

        return func, calls

    def test_first_call_executes_function(self):
        func, calls = self.make_counted(timeout=10)
        self.assertEqual("result-1", func(1, key="v"))
        self.assertEqual([((1,), {"key": "v"})], calls)

    def test_call_within_timeout_returns_cached_result(self):
        func, calls = self.make_counted(timeout=10)
        func()
        self.clock.advance(5)
        self.assertEqual("result-1", func())
        self.assertEqual(1, len(calls))

    def test_cache_still_valid_at_exact_timeout_boundary(self):
        # Expiry uses a strict ">" comparison: elapsed == timeout is still a hit.
        func, calls = self.make_counted(timeout=10)
        func()
        self.clock.advance(10)
        self.assertEqual("result-1", func())
        self.assertEqual(1, len(calls))

    def test_reexecutes_after_timeout_expires(self):
        func, calls = self.make_counted(timeout=10)
        func()
        self.clock.advance(10.001)
        self.assertEqual("result-2", func())
        self.assertEqual(2, len(calls))
        # The fresh result is cached again from the new timestamp.
        self.clock.advance(9)
        self.assertEqual("result-2", func())
        self.assertEqual(2, len(calls))

    def test_cache_ignores_arguments(self):
        # Real behavior: a single cache slot per decorated function, NOT keyed by arguments.
        func, calls = self.make_counted(timeout=10)
        self.assertEqual("result-1", func("a"))
        self.assertEqual("result-1", func("b", extra=True))
        self.assertEqual([(("a",), {})], calls)

    def test_dynamic_timeout_doubles_when_function_slower_than_timeout(self):
        func, calls = self.make_counted(timeout=1, dynamic_timeout=True, runtime=2)
        func()  # runtime 2 > timeout 1 -> timeout becomes 2; timestamp taken after execution
        self.clock.advance(1.5)  # would be a miss with the original timeout of 1
        self.assertEqual("result-1", func())
        self.assertEqual(1, len(calls))
        self.clock.advance(1)  # 2.5s since cached > doubled timeout 2
        self.assertEqual("result-2", func())  # runtime 2 is not > 2 -> no further doubling
        self.assertEqual(2, len(calls))
        self.clock.advance(2.5)
        self.assertEqual("result-3", func())
        self.assertEqual(3, len(calls))

    def test_dynamic_timeout_not_doubled_for_fast_function(self):
        func, calls = self.make_counted(timeout=1, dynamic_timeout=True, runtime=0.5)
        func()
        self.clock.advance(1.5)  # a doubled timeout (2) would make this a hit
        self.assertEqual("result-2", func())
        self.assertEqual(2, len(calls))

    def test_slow_function_does_not_double_timeout_without_dynamic_timeout(self):
        func, calls = self.make_counted(timeout=1, runtime=2)
        func()
        self.clock.advance(1.5)
        self.assertEqual("result-2", func())
        self.assertEqual(2, len(calls))

    def test_clear_cache_forces_reexecution(self):
        func, calls = self.make_counted(timeout=10)
        func.clear_cache()  # empty cache: must not raise
        self.assertEqual("result-1", func())
        func.clear_cache()
        self.assertEqual("result-2", func())  # well within timeout, yet re-executed
        self.assertEqual(2, len(calls))
        func.clear_cache()
        func.clear_cache()  # repeated clear on an already-empty cache must not raise

    def test_wraps_preserves_function_metadata(self):
        @memoize(10)
        def documented():
            """Docstring of the wrapped function."""

        self.assertEqual("documented", documented.__name__)
        self.assertEqual("Docstring of the wrapped function.", documented.__doc__)
        self.assertTrue(callable(documented.clear_cache))
