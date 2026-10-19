# 002 — Tests for util/cache.py memoize()

**Date**: 2026-10-19
**Tool**: Claude Code (main session + one subagent per target file, run in parallel)
**Model**: Claude Opus 5.5
**Iterations**: 0

## Prompt

**2026-10-19 12:38**

ok und das? https://l3gj0n.github.io/ai_supported_software_development_hs_aalen/en/exercises/03-brownfield-locust-exercises/

**2026-10-19 12:42**

(Prompt written by the main Claude Code session after reading `locust/util/cache.py`,
sent to a subagent — shortened only in formatting.)

Create a NEW test file `locust/test/test_cache.py` with behavioral unit tests for the
`memoize()` decorator in `locust/util/cache.py`. Read that source first. Important actual
behavior (verify it yourself):
- The cache is a single slot per decorated function — it is NOT keyed by arguments. A
  second call with different args within the timeout returns the first call's result.
  Document this real behavior in a test rather than asserting an argument-keyed cache.
- `dynamic_timeout=True` doubles `timeout` only when the wrapped function's own runtime
  exceeds the current timeout — not on every miss. Test both: slow function → timeout
  doubles, fast function → no doubling.
- `clear_cache()` forces re-execution; calling it on an empty cache must not raise.
- `functools.wraps` preserves `__name__`/`__doc__`.

Cases required: cache miss, cache hit (verified with a call counter), timeout expiry,
dynamic_timeout doubling, clear_cache behavior. Make tests deterministic and fast: patch
`locust.util.cache.time` instead of real sleeping. Use unittest.TestCase style like the
rest of the suite. Each test should fail if the corresponding logic were broken (e.g. `>`
changed to `<`, doubling removed). Prefer ~6–9 meaningful tests over many shallow ones.
Validate with pytest, pytest-cov and ruff; argue which test catches which mutation.

## What happened

### Setup fix: `pytest-cov` was missing

The coverage command from the exercise failed with
`pytest: error: unrecognized arguments: --cov=...` — `pytest-cov` is not a dependency of
this repo. Fixed with `uv add --group test pytest-cov` (adds it to the `test` dependency
group in `pyproject.toml` and updates `uv.lock`). Part of this commit.

Also noticed: `--cov=locust/util/cache` (path to a single module) reports
"No data to report"; the dotted form `--cov=locust.util.cache` works.

### The exercise description is wrong about memoize

Reading the code before prompting paid off. The exercise says the cache key is
argument-based and that `dynamic_timeout` doubles the timeout on each miss. Neither is
true:

- There is exactly one cache slot per decorated function; arguments are ignored.
- The timeout only doubles when the function itself runs longer than the timeout.

The prompt therefore asked the AI to test the *real* behavior.

### Accepted output

10 tests in a new file `locust/test/test_cache.py` (no existing test file was changed).
A `FakeClock` replaces `time()`, so tests run in ~0.3 s without sleeping. Tests cover:
miss, hit, the exact timeout boundary (strict `>`), expiry, the argument-ignoring cache,
dynamic doubling (slow function), no doubling (fast function / flag off), `clear_cache()`
and `functools.wraps` metadata.

Mutation reasoning from the AI (checked by reading the tests): removing the doubling
breaks `test_dynamic_timeout_doubles_when_function_slower_than_timeout`, `>` → `>=` breaks
`test_cache_still_valid_at_exact_timeout_boundary`, and `clear_cache` not deleting `time`
breaks `test_clear_cache_forces_reexecution`.

### Rejected / not done

- A per-argument cache test — would assert behavior the code doesn't have.
- Real-sleep timing tests — slow and flaky.
- A test for the shared-cache bug below — it would lock in a bug as intended behavior.

### Findings in memoize (not fixed — out of scope)

- If one `memoize(5)` object decorates two functions, they share one cache slot.
- The doubled timeout never shrinks again.
- Expiry counts from when the function *finished*, not when it started.
- Not greenlet-safe: two callers can both see a miss.

### Coverage

| File | Before | After |
|---|---|---|
| `locust/util/cache.py` | 10 % | 100 % (lines + branches) |

`uv run ruff check .` and `uv run ruff format --check .` pass.
