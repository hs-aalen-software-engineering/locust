from locust.util.exception_handler import retry

import unittest
from unittest import mock

LOGGER_NAME = "locust.util.exception_handler"
SLEEP_PATH = "locust.util.exception_handler.time.sleep"


def make_flaky(failures, result="ok", exc_factory=lambda i: ValueError(f"boom {i}")):
    """Return a Mock that raises `failures` exceptions before returning `result`."""
    side_effects = [exc_factory(i) for i in range(failures)] + [result]
    return mock.Mock(side_effect=side_effects)


@mock.patch(SLEEP_PATH)
class TestRetry(unittest.TestCase):
    def test_success_on_first_try_does_not_sleep(self, mock_sleep):
        func = mock.Mock(return_value="result")
        wrapped = retry()(func)

        self.assertEqual("result", wrapped())
        self.assertEqual(1, func.call_count)
        mock_sleep.assert_not_called()

    def test_success_after_failures_sleeps_with_delays_in_order(self, mock_sleep):
        func = make_flaky(failures=2, result="finally")
        wrapped = retry(delays=(1, 3, 5))(func)

        with self.assertLogs(LOGGER_NAME, level="INFO"):
            self.assertEqual("finally", wrapped())

        self.assertEqual(3, func.call_count)
        self.assertEqual([mock.call(1), mock.call(3)], mock_sleep.call_args_list)

    def test_exhausted_retries_reraise_original_exception(self, mock_sleep):
        errors = [ValueError(f"boom {i}") for i in range(4)]
        func = mock.Mock(side_effect=errors)
        wrapped = retry(delays=(1, 3, 5))(func)

        with self.assertLogs(LOGGER_NAME, level="INFO"):
            with self.assertRaises(ValueError) as ctx:
                wrapped()

        # The exception from the last attempt is re-raised unchanged, not wrapped
        self.assertIs(errors[-1], ctx.exception)
        self.assertEqual("boom 3", str(ctx.exception))
        self.assertEqual(4, func.call_count)
        self.assertEqual([mock.call(1), mock.call(3), mock.call(5)], mock_sleep.call_args_list)

    def test_non_matching_exception_propagates_immediately(self, mock_sleep):
        error = TypeError("not retried")
        func = mock.Mock(side_effect=error)
        wrapped = retry(delays=(1, 3), exception=ValueError)(func)

        with self.assertRaises(TypeError) as ctx:
            wrapped()

        self.assertIs(error, ctx.exception)
        self.assertEqual(1, func.call_count)
        mock_sleep.assert_not_called()

    def test_matching_exception_subclass_is_retried(self, mock_sleep):
        # UnicodeDecodeError is a subclass of ValueError and must be caught by exception=ValueError
        func = make_flaky(
            failures=1,
            exc_factory=lambda i: UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad"),
        )
        wrapped = retry(delays=(2,), exception=ValueError)(func)

        with self.assertLogs(LOGGER_NAME, level="INFO"):
            self.assertEqual("ok", wrapped())

        self.assertEqual(2, func.call_count)
        mock_sleep.assert_called_once_with(2)

    def test_args_and_kwargs_are_forwarded_on_every_attempt(self, mock_sleep):
        func = make_flaky(failures=1)
        wrapped = retry(delays=(1,))(func)

        with self.assertLogs(LOGGER_NAME, level="INFO"):
            wrapped("a", 2, key="value")

        self.assertEqual(
            [mock.call("a", 2, key="value"), mock.call("a", 2, key="value")],
            func.call_args_list,
        )

    def test_logs_each_retry_and_final_failure(self, mock_sleep):
        func = make_flaky(failures=3)
        wrapped = retry(delays=(1, 3))(func)

        with self.assertLogs(LOGGER_NAME, level="INFO") as logs:
            with self.assertRaises(ValueError):
                wrapped()

        info_messages = [r.getMessage() for r in logs.records if r.levelname == "INFO"]
        self.assertEqual(
            [
                "Exception found on retry 1: -- retry after 1s",
                "Exception found on retry 2: -- retry after 3s",
                "Retry failed after 2 times.",
            ],
            info_messages,
        )
        # Each caught exception is also logged with its traceback via logger.exception
        error_records = [r for r in logs.records if r.levelname == "ERROR"]
        self.assertEqual(2, len(error_records))
        self.assertTrue(all(r.exc_info is not None for r in error_records))

    def test_empty_delays_means_no_retry(self, mock_sleep):
        error = ValueError("once")
        func = mock.Mock(side_effect=error)
        wrapped = retry(delays=())(func)

        with self.assertLogs(LOGGER_NAME, level="INFO") as logs:
            with self.assertRaises(ValueError) as ctx:
                wrapped()

        self.assertIs(error, ctx.exception)
        self.assertEqual(1, func.call_count)
        mock_sleep.assert_not_called()
        self.assertEqual(["Retry failed after 0 times."], [r.getMessage() for r in logs.records])

    def test_delays_as_list_raises_type_error(self, mock_sleep):
        # Documents current behavior: `delays + (None,)` only works for tuples.
        # The error surfaces at call time, not at decoration time, and the
        # wrapped function is never invoked.
        func = mock.Mock(return_value="never")
        wrapped = retry(delays=[1, 2])(func)

        with self.assertRaises(TypeError):
            wrapped()

        func.assert_not_called()
        mock_sleep.assert_not_called()
