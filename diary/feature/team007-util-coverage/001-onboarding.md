# 001 — Onboarding and Exploration

**Date**: 2026-10-19
**Tool**: Claude Code
**Model**: Claude Opus 5.5
**Iterations**: 2

## Prompt

**2026-10-19 12:20**

kannst du das bitte umsetzen, cloned ist es ja schon
https://l3gj0n.github.io/ai_supported_software_development_hs_aalen/en/exercises/03-locust-exploration/

(Claude Code split this into two parallel subagents: one for setup/tests/locustfile,
one for the onboarding questions below.)

Onboarding questions asked:

1. What is the high-level architecture?
2. How does a user request flow from the `@task` method to the stats report?
3. What are the most important files to read first?
4. Compare the findings with `CLAUDE.md` — where does it lack detail, where is it wrong?
5. What does "requests per second" mean here? Is a 150 ms median good or bad?
   Why does RPS fluctuate? What happens at 50 users?

**2026-10-19 12:30**

Team name: Team007 — work locally only for now.

## What I Learned

### Architecture

- `locust/main.py:main()` parses options, builds an `Environment` (`env.py`), creates a
  runner (`create_local_runner` / `create_master_runner` / `create_worker_runner`) and
  the Flask web UI (`create_web_ui`).
- Runner hierarchy in `runners.py`: `Runner` → `LocalRunner`, and
  `DistributedRunner` → `MasterRunner` / `WorkerRunner` (master/worker talk over ZMQ,
  `locust/rpc/`).
- Every simulated user is one gevent greenlet; components are decoupled via
  `EventHook`s in `event.py`.

### Request flow: `@task` → stats report

1. `@task(n)` sets a weight; `get_tasks_from_base_classes` puts the method into the task
   list *n* times — weights work by duplication, then `random.choice`.
2. `TaskSet.run()` loops: `get_next_task()` → `execute_next_task()` → `wait()`.
3. `HttpUser` builds an `HttpSession` wired to `environment.events.request`.
4. `HttpSession.request()` times the call with `perf_counter` and wraps it in a
   `ResponseContextManager`; its `__exit__` decides success/failure and fires the
   `request` event.
5. `Runner.on_request` → `RequestStats.log_request` → `StatsEntry.log()` (per-second
   counts, response times rounded into buckets).
6. Distributed: workers send serialized stats every 3 s (`report_to_master`), the master
   merges them via `worker_report` → `StatsEntry.extend()`.
7. Output: console `print_stats` every 2 s; the React UI polls `/stats/requests` every 2 s.

### Files to read first

`user/task.py`, `user/users.py`, `clients.py`, `stats.py`, `runners.py`, `main.py`.

### Load-test concepts

- RPS = completed requests per second, averaged over roughly the last 10 s
  (`current_rps`), not tasks per second.
- 150 ms median is fine for a typical API backed by a DB, slow for static/cached content.
  Percentiles (p95/p99) and the trend under load matter more than the median.
- RPS fluctuates because of the random `between(1, 3)` wait, ramp-up, varying response
  times, the short averaging window and gevent scheduling.
- Rough estimate: one cycle ≈ 2 s wait + response time ≈ 2.15 s → ~0.47 req/s per
  user → ~5 RPS at 10 users, ~23 RPS at 50 users. RPS grows linearly until the target
  or the Locust process (CPU warning at 90 %) becomes the bottleneck; then latency rises.

### What the AI found vs. `CLAUDE.md`

`CLAUDE.md` is a good map, but the AI found several inaccuracies by checking the code:

- `/api/stats`, `/api/start`, `/api/stop` don't exist — real routes are
  `/stats/requests`, `/swarm` (POST) and `/stop` (also wrong in `copilot-instructions.md`).
- The UI does not use WebSockets; it polls over HTTP.
- `TestRequestStats::test_log_request` doesn't exist.
- `mock_locustfile()` lives in `locust/test/mock_locustfile.py`, not `util.py`.
- Test counts are off (27 test files, ~628 tests instead of 28 / "700+").
- Not mentioned at all: task weights by duplication, `DistributedRunner`,
  `user/inspectuser.py` (one of our coverage targets!), `contrib/oai.py`,
  `opentelemetry.py`.

Lesson: the AI's answers were more detailed than `CLAUDE.md` because it was told to
verify against the source — the context file itself can be outdated, so cite file and
line numbers and double-check.

### Setup issues and fixes

- First clone was accidentally from upstream `locustio/locust` instead of the course copy
  `hs-aalen-software-engineering/locust` — fixed by re-pointing `origin` (upstream kept
  as `upstream`) and resetting `master` to `origin/master`.
- `uv sync` worked first try (uv 0.11.26, Python 3.14.7).
- `pre-commit` was not installed → `uv tool install pre-commit`, then `pre-commit install`.
  Note: the config also has a local `yarn lint` hook for `locust/webui/`, which needs yarn.
- Tests: `test_env.py` 9 passed, `test_tags.py` 15 passed.
- Web UI returned HTTP 500 (`index.html` missing) because the React frontend wasn't
  built. Node 26 no longer ships `corepack`, and yarn wasn't installed → ran yarn via
  `npx --yes corepack@latest yarn install` and `... yarn build` in `locust/webui`;
  afterwards the UI loaded fine.

### Observed run (10 users, spawn rate 2, 30 s, httpbin.org)

| Name | Requests | Failures | Median | Avg | RPS |
|---|---|---|---|---|---|
| GET /get | 28 | 0 | 150 ms | 279 ms | 0.98 |
| GET /headers | 94 | 0 | 150 ms | 269 ms | 3.29 |
| Aggregated | 122 | 0 | 150 ms | 271 ms | 4.26 |

p95 700 ms, p99 1200 ms. `/headers` gets ~3× the requests of `/get` (weight 3 vs 1),
and the aggregated ~4.3 RPS matches the predicted ~5 RPS for 10 users (still ramping up
during the first 5 s). The median is low, but the high p95/p99 show httpbin.org's
long-tail latency.
