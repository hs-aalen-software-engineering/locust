"""
Performance benchmarks for Locust refactoring exercises.

Measures operations/second for the refactoring targets in each exercise package.
Run via: make benchmark  (or: uv run python benchmarks/run_benchmarks.py)

Produces stable, copy-pasteable output for PR descriptions.
"""

from __future__ import annotations

import statistics
import time


def _bench(func, iterations=5000, warmup=500, rounds=5):
    """
    Run *func* in a tight loop and return median ops/sec across *rounds*.

    Each round executes *iterations* calls. The first *warmup* calls per round
    are discarded. Returns (median_ops_sec, all_ops_sec_values).
    """
    results = []
    for _ in range(rounds):
        # warmup
        for _ in range(warmup):
            func()

        start = time.perf_counter()
        for _ in range(iterations):
            func()
        elapsed = time.perf_counter() - start

        ops = iterations / elapsed if elapsed > 0 else float("inf")
        results.append(ops)

    return statistics.median(results), results


def _fmt(ops):
    """Format ops/sec with thousands separator."""
    return f"{int(ops):,}"


# ---------------------------------------------------------------------------
# Package A: log.py — setup_logging()
# ---------------------------------------------------------------------------


def bench_setup_logging():
    from locust.log import setup_logging

    import logging
    import logging.config

    def run():
        setup_logging("WARNING")
        # Reset so repeated calls don't accumulate handlers
        logging.root.handlers.clear()
        logging.Logger.manager.loggerDict.clear()

    return _bench(run, iterations=2000, warmup=200, rounds=5)


# ---------------------------------------------------------------------------
# Package B: stats.py — StatsEntry.log() and StatsEntry.extend()
# ---------------------------------------------------------------------------


def bench_stats_log():
    from locust.stats import RequestStats

    request_stats = RequestStats()
    # Access via entries dict triggers __missing__ to auto-create the StatsEntry
    entry = request_stats.entries[("/api/test", "GET")]

    response_times = list(range(10, 510, 10))  # 50 different response times
    length = len(response_times)

    idx = 0

    def run():
        nonlocal idx
        entry.log(response_times[idx % length], 256)
        idx += 1

    return _bench(run, iterations=50000, warmup=1000, rounds=5)


def bench_stats_extend():
    from locust.stats import RequestStats

    def make_populated_entry(stats, name, n_requests=200):
        entry = stats.entries[(name, "GET")]
        for i in range(n_requests):
            entry.log(50 + (i % 400), 128 + (i % 512))
        return entry

    source_stats = RequestStats()
    source_entry = make_populated_entry(source_stats, "/api/source")

    def run():
        target_stats = RequestStats()
        target_entry = make_populated_entry(target_stats, "/api/target", n_requests=50)
        target_entry.extend(source_entry)

    return _bench(run, iterations=1000, warmup=100, rounds=5)


# ---------------------------------------------------------------------------
# Package C: user/task.py — filter_tasks_by_tags()
# ---------------------------------------------------------------------------


def bench_filter_tasks_by_tags():
    from locust.user.task import TaskSet, filter_tasks_by_tags

    tag_names = [
        "api",
        "web",
        "auth",
        "db",
        "cache",
        "search",
        "upload",
        "download",
        "admin",
        "public",
        "slow",
        "fast",
        "critical",
        "smoke",
        "regression",
        "integration",
        "unit",
        "e2e",
        "perf",
        "security",
    ]

    # Build a TaskSet with ~20 tagged tasks
    task_funcs = []
    for i in range(20):
        fn_name = f"task_{i}"

        def make_task(n):
            def the_task(self):
                pass

            the_task.__name__ = fn_name
            the_task.__qualname__ = fn_name
            the_task.locust_task_weight = 1
            # assign 1-3 tags per task
            the_task.locust_tag_set = {tag_names[n % 20], tag_names[(n + 7) % 20]}
            return the_task

        task_funcs.append(make_task(i))

    class OriginalTaskSet(TaskSet):
        tasks = list(task_funcs)

    include_tags = {"api", "auth", "critical"}
    exclude_tags = {"slow", "regression"}

    def run():
        # Reset tasks before each filter (filter_tasks_by_tags mutates in place)
        OriginalTaskSet.tasks = list(task_funcs)
        filter_tasks_by_tags(OriginalTaskSet, tags=include_tags, exclude_tags=exclude_tags)

    return _bench(run, iterations=5000, warmup=500, rounds=5)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print()
    print("=== Locust Performance Benchmark ===")
    print()

    # Package A
    ops, _ = bench_setup_logging()
    print("Package A targets:")
    print(f"  log.py: setup_logging()          — {_fmt(ops)} ops/sec")
    print()

    # Package B
    ops_log, _ = bench_stats_log()
    ops_extend, _ = bench_stats_extend()
    print("Package B targets:")
    print(f"  stats.py: StatsEntry.log()       — {_fmt(ops_log)} ops/sec")
    print(f"  stats.py: StatsEntry.extend()    — {_fmt(ops_extend)} ops/sec")
    print()

    # Package C
    ops_filter, _ = bench_filter_tasks_by_tags()
    print("Package C targets:")
    print(f"  task.py: filter_tasks_by_tags()  — {_fmt(ops_filter)} ops/sec")
    print()
    print("=====================================")
    print()


if __name__ == "__main__":
    main()
