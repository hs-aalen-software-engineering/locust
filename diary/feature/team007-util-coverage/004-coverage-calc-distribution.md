# 004 — Tests for user/inspectuser.py _calc_distribution()

**Date**: 2026-10-19
**Tool**: Claude Code (subagent, run in parallel with 002 and 003)
**Model**: Claude Opus 5.5
**Iterations**: 0

## Prompt

**2026-10-19 12:42**

(Same user prompt as in 002; this prompt was written by the main Claude Code session and
sent to a subagent.)

Create a NEW test file `locust/test/test_inspectuser.py` with behavioral unit tests for
`_calc_distribution(user_classes, num_users)` in `locust/user/inspectuser.py`. Read the
source, and read `locust/test/test_taskratio.py` to see existing coverage and style (don't
duplicate its tests). Check how `weight` and `fixed_count` are defined on `User` and how
`num_users` reaches this function so expectations are realistic.

Behaviors to test:
- equal weights: two classes weight 1, num_users=10 → 5/5.
- mixed weights: 1 and 3, num_users=8 → 2/6; also a case where rounding matters
  (document that the sum can differ from num_users).
- fixed_count users, and fixed_count larger than num_users (max(0, …) clamp).
- zero/None users: defaults to total_weight; with a fixed_count class → defaults to 1.
- only fixed_count classes → no ZeroDivisionError.
- Report (do not fix) what happens if all weighted classes have weight 0.
Define throwaway User subclasses inside tests. unittest.TestCase style. Add 1–2 tests for
`get_ratio` / `print_task_ratio_json` only if cheap and meaningful. Target ≥ 80 %.

## What happened

### Accepted output

12 tests in a new file `locust/test/test_inspectuser.py` (the existing
`test_taskratio.py` was not changed). A helper `make_user(name, weight, fixed_count)`
builds throwaway `User` classes.

`_calc_distribution`: equal and mixed weights, rounding that makes the total differ from
`num_users` (3 × 3.33 → 9), Python's banker's rounding (`round(2.5) == 2`), fixed count
subtracted first, a fixed class's weight is ignored, clamping to 0, the `0`/`None`
defaults, and only-fixed classes.

`print_task_ratio_json` / `print_task_ratio`: parse the JSON / text output and check the
ratios (25 % / 75 %) end-to-end.

### Rejected

- More `get_ratio` tests — `test_taskratio.py` already covers nested TaskSets.
- `assertRaises(ZeroDivisionError)` for weight 0 — would lock in a bug as intended.
- `LocustTestCase` — no Environment needed.

### Findings (not fixed — out of scope)

- If all weighted classes have `weight = 0`, `_calc_distribution` raises
  `ZeroDivisionError`. According to the AI's reading of `main.py` this is reachable with
  `--show-task-ratio` when a `fixed_count` class exists next to weight-0 classes (not
  verified via the CLI).
- Displayed user counts may not add up to the requested number of users because each
  class is rounded separately.

### Coverage

| File | Before | After |
|---|---|---|
| `locust/user/inspectuser.py` | 60 % | 100 % (target ~80 %) |

## Final check for all three files

```
uv run pytest locust/test/test_util.py locust/test/test_log.py locust/test/test_taskratio.py \
  locust/test/test_cache.py locust/test/test_exception_handler.py locust/test/test_inspectuser.py \
  --cov=locust.util.cache --cov=locust.util.exception_handler --cov=locust.user.inspectuser \
  --cov-branch --cov-report=term-missing --cov-report=html -q
```

42 passed; `ruff check .` and `ruff format --check .` pass.

## Reflection

Splitting the three files across parallel subagents worked because they are independent.
The most valuable step was reading the source *before* prompting: the exercise text
describes `memoize()` incorrectly, and a prompt copied from it would have produced tests
that assert non-existent behavior. All three AIs also reported real weaknesses in the code
(shared memoize cache, `retry` with lists, division by zero) instead of just chasing
coverage numbers.
