# -*- coding: utf-8 -*-
"""Real-time performance benchmarking and execution timers for ScarTools operations."""

from __future__ import absolute_import, division, print_function

import time


class ExecutionTimer(object):
    """Context manager to profile execution time and report millisecond benchmarks."""

    def __init__(self, operation_name="Operation", item_count=None, emit_to_log=True, source=None):
        self.operation_name = operation_name
        self.item_count = item_count
        self.emit_to_log = emit_to_log
        self.source = source or "Benchmark"
        self.start_time = 0.0
        self.end_time = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        self.elapsed_ms = (self.end_time - self.start_time) * 1000.0

        if self.emit_to_log and exc_type is None:
            from .logging import emit_log
            emit_log(self.summary_text(), level="info", source=self.source)

    def summary_text(self):
        if self.item_count is not None:
            return "⚡ {} completed in {:.1f}ms ({} item(s))".format(
                self.operation_name, self.elapsed_ms, self.item_count
            )
        return "⚡ {} completed in {:.1f}ms".format(self.operation_name, self.elapsed_ms)


def time_operation(operation_name="Operation", item_count=None, source=None):
    """Create an ExecutionTimer context manager."""
    return ExecutionTimer(operation_name=operation_name, item_count=item_count, source=source)


__all__ = ["ExecutionTimer", "time_operation"]
