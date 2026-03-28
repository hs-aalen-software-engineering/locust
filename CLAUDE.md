# Locust Development Guide

> **Teaching repository.** This is a modified copy of [locustio/locust](https://github.com/locustio/locust),
> used in the course "AI-Supported Software Development" at Hochschule Aalen.
> GitHub Actions are disabled. Branch protection is enabled on `master` (1 review required).

## Table of Contents

- [Collaboration Principles](#collaboration-principles)
- [High-Level Overview](#high-level-overview)
- [Key Directories](#key-directories)
- [Key Files to Understand First](#key-files-to-understand-first)
- [Quick Start](#quick-start)
- [Commands](#commands)
- [Testing Details](#testing-details)
- [Git Workflow](#git-workflow)
- [Development Workflows](#development-workflows)
- [Common Patterns](#common-patterns)
- [Codebase Navigation](#codebase-navigation)
- [Debugging](#debugging)
- [Troubleshooting](#troubleshooting)
- [What NOT to Touch](#what-not-to-touch)
- [AI Diary](#ai-diary)

## Collaboration Principles

**Be direct and accurate.** Evaluate code, suggestions, and approaches on
their technical merits. If something is wrong, unclear, or could be better,
say so constructively. Technical correctness matters more than being agreeable.

**Understand before changing.** Read the relevant source code before proposing
modifications. Locust is a mature codebase with intentional design decisions —
understand *why* something is the way it is before suggesting a different
approach. When in doubt, look at how similar things are already done in the code.

**Research, plan, implement, validate.** For any non-trivial change:

1. **Research** — Read the relevant modules, tests, and examples
2. **Plan** — Outline the approach before writing code
3. **Implement** — Make focused, minimal changes
4. **Validate** — Run tests and linting before considering the work done

**Keep changes minimal.** Do not make drive-by improvements, unrelated
refactors, or style changes in the same commit as a functional change.
One logical change per commit, one purpose per PR.

## High-Level Overview

Locust is a **load/performance testing framework** written in Python. Users
define virtual user behavior in plain Python classes, and Locust spawns
thousands of concurrent greenlets (via gevent) to simulate traffic against a
target system. It provides a real-time web UI for controlling tests and viewing
results, and supports distributed execution across multiple machines via ZeroMQ.

### Architecture

```
main.py  →  Environment  →  Runner  →  Users (greenlets)
                │                │              │
                │                │              ├── @task methods
                │                │              └── HttpSession / FastHttpSession
                │                │
                │                ├── UsersDispatcher (allocates users to workers)
                │                └── stats.RequestStats (collects metrics)
                │
                ├── Events (pub/sub hooks: request, test_start, test_stop, ...)
                ├── WebUI (Flask REST API + React frontend on :8089)
                └── LoadTestShape (optional programmatic load curves)
```

**Request data flow:** A User's `@task` method calls `self.client.get(url)` →
`HttpSession` measures the response time → fires `environment.events.request` →
`RequestStats` logs it → the web UI polls `/api/stats` to display charts.

**Runner hierarchy:** `Runner` (abstract) → `LocalRunner` (single process) /
`MasterRunner` + `WorkerRunner` (distributed via ZMQ). The `MasterRunner` sends
spawn commands and aggregates stats; each `WorkerRunner` executes users locally
and reports stats back every 3 seconds.

**Concurrency model:** Locust uses gevent greenlets — cooperative, lightweight
coroutines. A single process can handle thousands of concurrent simulated users.
All I/O is cooperative: `locust/__init__.py` monkey-patches the standard library
so that `time.sleep()`, `socket`, etc. yield to the gevent event loop instead
of blocking.

## Key Directories

```
locust/                     Main Python package
├── user/                   User model and task system
│   ├── users.py            User, HttpUser, PytestUser base classes
│   ├── task.py             @task, @tag decorators, TaskSet, DefaultTaskSet
│   ├── wait_time.py        between(), constant(), constant_pacing(), constant_throughput()
│   ├── sequential_taskset.py  SequentialTaskSet
│   └── markov_taskset.py   MarkovTaskSet with @transition
├── contrib/                Optional protocol-specific clients
│   ├── fasthttp.py         FastHttpUser (geventhttpclient, higher throughput)
│   ├── mqtt.py             MqttUser
│   ├── socketio.py         SocketIOUser
│   ├── postgres.py         PostgresUser
│   ├── mongodb.py          MongoDBUser
│   └── ...                 milvus, qdrant, dns
├── rpc/                    ZeroMQ master↔worker communication
│   ├── protocol.py         Message class (msgpack serialization)
│   └── zmqrpc.py           Server/Client wrappers
├── webui/                  React + TypeScript frontend (Vite, Yarn)
│   └── src/                Components, Redux store, hooks, styles
├── test/                   Test suite (~700+ test methods, 28 files)
│   ├── testcases.py        LocustTestCase, WebserverTestCase base classes
│   ├── util.py             temporary_file(), patch_env(), get_free_tcp_port()
│   └── test_*.py           Test files matching source modules
├── __init__.py             Public API exports + gevent monkey-patching
├── main.py                 CLI entry point (locust command)
├── env.py                  Environment — central orchestration object
├── runners.py              LocalRunner, MasterRunner, WorkerRunner
├── dispatch.py             User-to-worker distribution algorithm (Kullback-Leibler)
├── stats.py                Request statistics collection and aggregation
├── event.py                EventHook pub/sub system
├── web.py                  Flask web UI + REST API endpoints
├── clients.py              HttpSession (requests.Session with stats integration)
├── shape.py                LoadTestShape base class for custom load profiles
├── argument_parser.py      CLI argument definitions (all --flags)
├── exception.py            StopUser, InterruptTaskSet, RescheduleTask, etc.
├── html.py                 HTML report generation
└── log.py                  Logging configuration

docs/                       Sphinx/RST documentation (builds to ReadTheDocs)
examples/                   40+ example locustfiles covering many use cases
pytest_locust/              pytest plugin for pytest-style locustfiles
```

## Key Files to Understand First

Start here when getting oriented in the codebase. Read these files (or at
least their docstrings, class definitions, and public methods) in this order:

1. **`locust/__init__.py`** — The public API surface. Shows everything users
   import from `locust` (User, HttpUser, task, between, events, etc.). Also
   does gevent monkey-patching, which must happen before any stdlib imports.

2. **`locust/user/users.py`** — `User` and `HttpUser` classes. Understand the
   user lifecycle: `on_start()` → task loop → `on_stop()`. The `UserMeta`
   metaclass collects `@task`-decorated methods automatically.

3. **`locust/user/task.py`** — `@task` decorator, `@tag` decorator, `TaskSet`
   class. The `run()` method is the core execution loop: pick a task →
   execute → wait → repeat.

4. **`locust/event.py`** — `EventHook` and `Events`. Locust's pub/sub system.
   Every major lifecycle moment fires an event (request, test_start, test_stop,
   spawning_complete, etc.). Plugins and custom behavior hook in here.

5. **`locust/env.py`** — `Environment` class. The central configuration object
   that holds references to user classes, the runner, web UI, stats, and events.
   Factory methods: `create_local_runner()`, `create_master_runner()`, etc.

6. **`locust/runners.py`** — Runner hierarchy. `LocalRunner` for single-process,
   `MasterRunner`/`WorkerRunner` for distributed mode. Controls user
   spawning/stopping, stats collection, and the shape worker loop.

7. **`locust/stats.py`** — `RequestStats` and `StatsEntry`. Collects per-request
   metrics (response time, count, errors) with histogram bucketing and
   percentile calculation. `StatsCSV` handles CSV export.

8. **`locust/web.py`** — Flask-based web UI. REST endpoints (`/api/stats`,
   `/api/start`, `/api/stop`, etc.) and WebSocket updates. The React frontend
   in `locust/webui/` consumes these endpoints.

9. **`locust/clients.py`** — `HttpSession`, extends `requests.Session`. Wraps
   every HTTP call with timing measurement and fires the `request` event.
   The `catch_response` context manager allows manual pass/fail control.

10. **`locust/main.py`** — CLI entry point. Parses arguments, loads locustfiles,
    creates the Environment, starts the runner and web UI. Also handles
    `--processes` (multi-process mode via forking).

## Quick Start

### Prerequisites

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) (package manager)
- Node.js >= 22 + Yarn (only needed for frontend work)

### Setup

```bash
# Install all Python dependencies (creates .venv automatically)
make install
# or equivalently:
uv sync
```

### Running Locust

```bash
# Start with the web UI (opens at http://localhost:8089)
locust -f examples/locustfile.py --host http://example.com

# Run headless (no UI, command line only)
locust -f examples/locustfile.py --host http://example.com --headless -u 10 -r 2 -t 30s

# Distributed mode
locust -f file.py --master                           # on the master
locust -f file.py --worker --master-host <master-ip> # on each worker
```

## Commands

### Testing

```bash
# Run the full test suite
make test
# or:
pytest -vv locust/test

# Run a specific test file
pytest locust/test/test_stats.py

# Run a single test method
pytest locust/test/test_stats.py::TestRequestStats::test_log_request

# Run tests and stop on first failure
pytest -x locust/test
```

### Code Quality

```bash
# Lint and auto-format (Ruff)
hatch run lint:format

# Type checking (mypy)
hatch run lint:types

# Run both
hatch run lint:all
```

### Benchmarks

```bash
# Run performance benchmarks for refactoring exercise targets
make benchmark
# or:
uv run python benchmarks/run_benchmarks.py
```

The benchmark measures ops/sec for the refactoring targets in each exercise
package and the stats hot path. Students must include before/after numbers in
refactoring PRs to confirm no performance regressions.

| Benchmark | Package | What it measures |
| --------- | ------- | ---------------- |
| `setup_logging()` | A (Utilities) | Logging config dict construction |
| `StatsEntry.log()` | B (Statistics) | Per-request stats recording (hot path) |
| `StatsEntry.extend()` | B (Statistics) | Stats entry merging |
| `filter_tasks_by_tags()` | C (User Model) | Task filtering by tag sets |

### Frontend

```bash
# Install frontend dependencies
yarn webui:install

# Build the frontend (only needed if modifying web UI)
yarn webui:build

# Start frontend dev server (port 4000, hot reload)
yarn webui:dev
```

### Documentation

```bash
# Build Sphinx docs
make build_docs

# Serve docs locally
make serve_docs
```

## Testing Details

### Test Organization

All tests live in `locust/test/` (not a separate `tests/` directory). Each
test file corresponds to a source module:

| Source module  | Test file                              | What it covers                            |
| -------------- | -------------------------------------- | ----------------------------------------- |
| `runners.py`   | `test_runners.py` (~4500 lines)        | Local/Master/Worker runners, RPC, state   |
| `dispatch.py`  | `test_dispatch.py` (~4100 lines)       | User distribution algorithm               |
| `main.py`      | `test_main.py` (~1700 lines)           | CLI integration, end-to-end               |
| `web.py`       | `test_web.py`                          | REST endpoints, HTML, CSV export          |
| `stats.py`     | `test_stats.py`                        | Request logging, percentiles, aggregation |
| `clients.py`   | `test_fasthttp.py`, `test_http.py`     | HTTP client behavior                      |
| `user/users.py`| `test_locust_class.py`, `test_users.py`| User lifecycle, wait times                |
| `user/task.py` | `test_tags.py`                         | Task tagging and filtering                |
| `env.py`       | `test_env.py`                          | Environment, events, LoadTestShape        |

### Test Base Classes

Tests use `unittest.TestCase` style (not pytest fixtures). Two base classes
in `locust/test/testcases.py`:

- **`LocustTestCase`** — Standard base. `setUp()` creates a fresh `Environment`
  and `LocalRunner`, clears `sys.argv`, resets events. Use for unit tests.
- **`WebserverTestCase`** — Extends `LocustTestCase`. Starts a live Flask test
  server on a random port (`self.port`). Use for tests that make real HTTP
  requests.

The test Flask app (in `testcases.py`) provides endpoints like `/ultra_fast`,
`/slow`, `/redirect`, `/rest`, `/basic_auth`, etc.

### How to Write a Test

```python
from locust import User, task, constant
from locust.test.testcases import LocustTestCase

class TestMyFeature(LocustTestCase):
    def test_something(self):
        class MyUser(User):
            wait_time = constant(0)
            @task
            def my_task(self):
                pass

        user = MyUser(self.environment)
        # ... assertions
```

For HTTP tests, extend `WebserverTestCase` and use `self.port` for the server.

### Test Utilities

Defined in `locust/test/util.py`:

- `temporary_file(content)` — Context manager creating a temp file with content
- `patch_env(key, value)` — Context manager for environment variables
- `get_free_tcp_port()` — Find an unused TCP port
- `mock_locustfile()` — Context manager creating a temporary locustfile

For end-to-end CLI tests, `locust/test/subprocess_utils.py` provides
`TestProcess` — a wrapper that captures stdout/stderr and supports
`expect()`, `send_input()`, and `terminate()`.

### Testing Principles

- **Run tests before pushing.** `make test` must pass. There is no CI in this
  teaching repo — you are the CI.
- **Never fix a test by changing the assertion** if the assertion is correct.
  Fix the code instead.
- **When multiple tests fail**, examine all of them but focus on fixing the
  first one. Often later failures are cascading from the same root cause.
- **Keep mocking minimal.** Locust's test base classes provide real Environment
  and Runner instances. Prefer integration-style tests over heavy mocking.
- **Match the existing style.** Look at the test file for the module you're
  changing and follow the same patterns.

## Git Workflow

This is a teaching repository simulating open-source contribution. Follow
this workflow for all changes:

### Branch and PR Flow

1. **Create a feature branch** from `master`:
   ```bash
   git checkout master && git pull
   git checkout -b feature/<short-description>
   # or: fix/<short-description>, refactor/<short-description>
   ```
2. **Make your changes** — keep commits focused and atomic.
3. **Validate** before pushing:
   ```bash
   make test
   hatch run lint:format
   ```
4. **Push and open a PR** against `master`:
   ```bash
   git push -u origin feature/<short-description>
   ```
5. **Get a review** — branch protection requires 1 approval before merging.

### Commit and PR Conventions

- **Commit messages**: Clear, imperative mood ("Add retry logic", not "Added
  retry logic" or "Adding retry logic")
- **PR title**: Short, under 70 characters, imperative
- **PR description**: Explain *what* changed and *why*. Link related issues.
- **Scope**: One logical change per PR. Do not bundle unrelated fixes.
- **No force pushes**: Create new commits for review feedback. Squash happens
  at merge time.

## Development Workflows

### Adding a New User Type

1. Create a new class extending `User` (or `HttpUser` for HTTP-based) in the
   appropriate location
2. Look at `locust/contrib/` for examples of protocol-specific users (e.g.,
   `mqtt.py`, `postgres.py`)
3. Add tests in `locust/test/`
4. If the user type needs a new dependency, add it as an optional extra in
   `pyproject.toml`

### Adding a New Event Hook

1. Add the event to the `Events` class in `locust/event.py`
2. Fire it at the appropriate point in the lifecycle (runners, web, etc.)
3. Document it with a docstring following the existing style
4. Add a test verifying the event fires with the correct arguments

### Adding a CLI Argument

1. Add the argument definition in `locust/argument_parser.py`
2. Wire it up in `locust/main.py` where the argument is consumed
3. Look at existing arguments for naming conventions (the `--flag` name maps
   to `LOCUST_FLAG` env var automatically via configargparse)
4. Add tests in `locust/test/test_parser.py` or `test_main.py`

### Modifying the Web UI

1. Frontend source is in `locust/webui/src/` (React + TypeScript)
2. Backend API endpoints are in `locust/web.py` (Flask)
3. Start the frontend dev server: `yarn webui:dev` (port 4000)
4. After changes, rebuild: `yarn webui:build`
5. Run frontend tests: `yarn webui:test`
6. Run frontend lint: `yarn webui:lint`

### Modifying Statistics

1. Core stats logic is in `locust/stats.py` — `RequestStats` and `StatsEntry`
2. Stats are collected via the `request` event (see `event.py`)
3. CSV export is handled by `StatsCSV` / `StatsCSVFileWriter`
4. Web endpoints serving stats are in `locust/web.py` (`/api/stats`)
5. Tests in `locust/test/test_stats.py`

## Common Patterns

### Gevent Greenlets and Cooperative Concurrency

Everything in Locust runs in gevent greenlets. Key implications:

- `gevent.sleep()` yields to the event loop; `time.sleep()` also works
  because of monkey-patching, but `gevent.sleep()` is more explicit
- One greenlet per user — the `Runner` creates and manages them via
  `gevent.pool.Group`
- CPU-bound code blocks *all* greenlets in the process. Locust monitors
  this and emits `cpu_warning` events when usage exceeds thresholds.

### Metaclass-Based Task Collection

`UserMeta` and `TaskSetMeta` (metaclasses) scan class bodies for methods
decorated with `@task` and collect them into a `tasks` list with proper
weights. This is why you can define `@task(3)` on a method and it "just works"
— the metaclass reads `locust_task_weight` from each method.

### Event-Driven Extension

Locust's plugin architecture is built on `EventHook` (in `event.py`):
```python
@events.init.add_listener
def on_init(environment, **kwargs):
    # Runs after Environment is created
    pass
```

Key events: `init`, `test_start`, `test_stop`, `request`, `spawning_complete`,
`report_to_master`, `worker_report`, `quitting`. See `locust/event.py` for
the full list with argument signatures.

### The `catch_response` Pattern

For response validation beyond HTTP status codes:
```python
with self.client.get("/api/data", catch_response=True) as response:
    if response.json().get("status") != "ok":
        response.failure("Bad status in JSON body")
```

This uses `ResponseContextManager` in `clients.py`. Without `catch_response`,
only HTTP errors (4xx/5xx) are counted as failures.

### Control Flow via Exceptions

Locust uses exceptions for control flow within the user lifecycle:

- `StopUser` — Gracefully stop the current user
- `InterruptTaskSet` — Return to the parent TaskSet (for nested TaskSets)
- `RescheduleTask` / `RescheduleTaskImmediately` — Skip the wait, pick next task
- `StopTest` — Abort the entire test run

These are defined in `locust/exception.py` and caught in the task execution
loop in `user/task.py`.

### Wait Time Functions

Four built-in strategies in `locust/user/wait_time.py`:

- `between(min, max)` — Random uniform between min and max seconds
- `constant(seconds)` — Fixed wait
- `constant_pacing(seconds)` — Total time from task start (adaptive)
- `constant_throughput(rate)` — Target N task runs per second (adaptive)

Custom wait times are just callables returning a float (seconds).

## Codebase Navigation

### Where to Find Things

- **"How does X work?"** — Start with the matching file in `locust/`. The
  directory layout mirrors the architecture closely.
- **"How do I test X?"** — Look at `locust/test/test_<module>.py`. Tests are
  the best documentation for edge cases and expected behavior.
- **"Is there an example?"** — Check `examples/` (40+ files). Key examples:
  - `locustfile.py` — Quickstart (HttpUser, tasks, wait times, on_start)
  - `rest.py` — FastHttpUser with REST assertions
  - `custom_shape/` — Step load, double wave, staged profiles
  - `events.py` — Event hook usage
  - `extend_web_ui.py` — Adding custom web routes
  - `grpc/`, `mqtt/`, `socketio/` — Non-HTTP protocols
- **"What CLI options exist?"** — See `locust/argument_parser.py` or run
  `locust --help`.
- **"What events can I hook into?"** — See the `Events` class in
  `locust/event.py`.
- **"How does distributed mode work?"** — `locust/runners.py`
  (MasterRunner/WorkerRunner) + `locust/rpc/` (ZMQ messaging).

### Finding Similar Patterns

When implementing something new, find where something similar is already done:

- Adding an HTTP feature → look at `locust/clients.py` and `contrib/fasthttp.py`
- Adding a protocol client → look at any file in `locust/contrib/` (mqtt, postgres, etc.)
- Adding a web endpoint → look at existing routes in `locust/web.py`
- Adding a load shape → look at `examples/custom_shape/`
- Adding a wait time function → look at `locust/user/wait_time.py`

## Debugging

### Running a Single User (No Runner, No Web UI)

Locust provides a `run_single_user` helper for quick debugging:

```python
# At the bottom of your locustfile:
from locust import run_single_user
if __name__ == "__main__":
    run_single_user(MyUser)
```

Then run with `python locustfile.py` and step through with a debugger. See
`examples/debugging.py` and `examples/debugging_advanced.py`.

### Verbose Logging

```bash
# Set log level
locust -f file.py --loglevel DEBUG

# Or via environment variable
LOCUST_LOGLEVEL=DEBUG locust -f file.py
```

### Common Debug Approaches

- **Task not executing?** Check that the method has `@task` and that the class
  has `wait_time` set. Without `wait_time`, you get `MissingWaitTimeError`.
- **Stats not recording?** Verify the `request` event is firing. Custom clients
  must call `environment.events.request.fire(...)` manually.
- **Distributed workers not connecting?** Check that master and workers use the
  same `--master-port` (default 5557) and that firewalls allow ZMQ traffic.
- **High CPU / greenlets blocking?** Locust logs a warning when CPU exceeds
  a threshold. CPU-bound work in a task blocks all greenlets in that process.
  Use `--processes` to spread across cores, or offload heavy computation.

## Troubleshooting

### Setup Issues

**`make install` fails with "uv not found"**

- Install uv: `pip install uv` or see [docs.astral.sh/uv](https://docs.astral.sh/uv/)

**`ImportError` after install**

- Make sure you're using the project's venv: `uv sync` creates `.venv/`
- Activate it: `source .venv/bin/activate` (Linux/Mac) or `.venv\Scripts\activate` (Windows)

**`gevent` build errors on Windows**

- Locust depends on gevent, which requires a C compiler. Install
  Visual Studio Build Tools with the "C++ build tools" workload.

### Test Issues

**`ResourceWarning: unclosed socket`**

- These are suppressed in `LocustTestCase`. If you see them in your test,
  make sure you're extending the right base class.

**Tests hang or timeout**

- Likely a greenlet that never yields. Check for blocking I/O without
  gevent monkey-patching, or a `while True` loop missing `gevent.sleep()`.

**`Too many open files` error**

- `locust/test/__init__.py` increases `RLIMIT_NOFILE` to 10000 on Unix.
  On Windows, this limit is handled differently and rarely an issue.

### Coding Conventions

- **Line length**: 120 characters
- **Formatter/linter**: Ruff (handles both formatting and linting)
- **Import order**: `locust` imports must come first (before stdlib) because
  `__init__.py` does gevent monkey-patching. Ruff's isort is configured for
  this — let it handle import ordering.
- **Type checking**: mypy with `python_version = "3.10"` and
  `ignore_missing_imports = true`
- **No conftest.py**: Tests use base classes for setup/teardown, not pytest
  fixtures

## What NOT to Touch

- **`.github/workflows/`** — GitHub Actions are disabled in this teaching repo.
  Editing these files has no effect and clutters diffs.
- **`locust/webui/dist/`** — Built frontend artifacts. Regenerated by
  `yarn webui:build`.
- **`locust/_version.py`** — Auto-generated by hatch-vcs from git tags.
- **Docker/release files** (`Dockerfile*`, Makefile release targets) — Not
  relevant for course exercises.

## AI Diary

Every AI-assisted contribution to this repository is documented in an **AI
Diary** — a transparent log of prompts and the artifacts they produced. The
goal is traceability: reviewers, instructors, and future contributors can see
exactly what was asked, what was generated, and how many iterations it took.

### Why

In a course about AI-supported software development, making AI usage visible
matters. The diary ensures that AI contributions are traceable in the git
history, supports honest reflection on how AI tools are used, and helps the
team learn from each other's prompting strategies.

### Where entries live

```text
diary/<branch-name>/NNN-short-title.md
```

Each feature branch gets its own subfolder under `diary/`. Inside, entries are
numbered markdown files (e.g., `001-add-retry-logic.md`).

### Entry template

```markdown
# NNN — Short Title

**Date**: YYYY-MM-DD
**Tool**: [tool name, e.g., Claude Code, GitHub Copilot, Cursor]
**Model**: [model name, e.g., Claude Opus 4.6, GPT-4.1]
**Iterations**: [number of follow-up prompts needed]

## Prompt

**YYYY-MM-DD HH:MM**

[The full prompt text as given by the user.]

If there were follow-up prompts, add each with its own timestamp:

**YYYY-MM-DD HH:MM**

[Follow-up prompt text.]
```

### Commit convention

Every prompt that creates or modifies code artifacts results in its own commit
containing both the code changes and the corresponding diary entry:

```text
[diary] NNN — Short description of what was prompted
```

This way, `git log` shows a clear trail of AI interactions, and
`git show <hash>` reveals both what was produced and what was asked.

### Rule

Every AI-assisted code change **must** have a corresponding diary entry
committed alongside it. No exceptions — this is how we keep AI usage
transparent in this teaching repository.
