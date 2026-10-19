# 003 — Tests for util/exception_handler.py retry()

**Date**: 2026-10-19
**Tool**: Claude Code (subagent, run in parallel with 002 and 004)
**Model**: Claude Opus 5.5
**Iterations**: 0

## Prompt

**2026-10-19 12:42**

(Same user prompt as in 002; this prompt was written by the main Claude Code session and
sent to a subagent.)

Create a NEW test file `locust/test/test_exception_handler.py` with behavioral unit tests
for the `retry()` decorator in `locust/util/exception_handler.py`. Read the source first
and check where it is used in the codebase (grep) to understand its intended use.

Behaviors to test:
- success on first try: function called once, return value passed through, no sleep.
- success on retry: fails n times then succeeds → returns the value, called n+1 times,
  `time.sleep` called with the delays in order.
- failure after retries exhausted: called len(delays)+1 times, the ORIGINAL exception is
  re-raised, sleep called with all delays.
- custom exception filtering: with `exception=ValueError`, a TypeError propagates
  immediately; a ValueError is retried.
- args/kwargs are forwarded.
- logging: the "Retry failed after N times." info message.
- empty delays tuple → no retry at all.
Optionally note that passing `delays` as a list raises TypeError and that the wrapper does
not use functools.wraps — report these as findings; do not fix source.

Make tests fast: patch `time.sleep` — never really sleep. unittest.TestCase style. Each
test must fail if the logic were broken. Prefer ~6–9 meaningful tests.

## What happened

### Context found by the AI

`retry()` is only used in `locust/rpc/zmqrpc.py` on `Client.send` / `send_to_client` with
the default delays `(1, 3, 5)`: a failing ZMQ send is tried 4 times and blocks up to 9 s.

### Accepted output

9 tests in a new file `locust/test/test_exception_handler.py`, `time.sleep` patched for
the whole class. They check: first-try success without sleeping, success after failures
with sleeps `1, 3` in order, the *same* exception object re-raised after all retries
(`assertIs`), non-matching exceptions propagate immediately, exception *subclasses* are
retried (`UnicodeDecodeError` is a `ValueError`), args/kwargs forwarded on every attempt,
exact log messages, empty `delays`, and `delays` as a list.

### Decision: keep `test_delays_as_list_raises_type_error`

This test documents current (arguably buggy) behavior: `delays + (None,)` only works for
tuples, and the error only appears when the decorated function is first called. Kept on
purpose so the pitfall is visible; a future fix will have to update this test
deliberately.

### Rejected

- A test that `__name__` is preserved — fails with the current code (no `functools.wraps`);
  reported as a finding instead.
- Real sleeps, tests through `zmqrpc.Client` (integration, needs sockets), checking every
  log line in every test (brittle), `KeyboardInterrupt` (adds little).

### Findings in retry (not fixed — out of scope)

- `delays` must be a tuple; a list fails only at call time.
- No `functools.wraps` → `Client.send.__name__ == "wrapper"`.
- Every failed attempt logs a full ERROR traceback, even if the next retry succeeds.

### Coverage

| File | Before | After |
|---|---|---|
| `locust/util/exception_handler.py` | 33 % (exercise page says 54 %) | 96 % |

The remaining partial branch `11->exit` (the `for` loop finishing without return/raise) is
unreachable: the final `None` entry always re-raises. 100 % is impossible without changing
the source.
