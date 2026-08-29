"""Structured, UI-neutral results shared by every ScarTools operation."""

from __future__ import print_function

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class OperationMessage:
    """One semantic message that can be rendered by any UI or logger."""

    level: str
    text: str
    code: str = ""
    context: dict = field(default_factory=dict)

    def as_dict(self):
        return {
            "level": self.level,
            "text": self.text,
            "code": self.code,
            "context": dict(self.context),
        }


@dataclass
class OperationResult:
    """Canonical return value for new suite services and controllers."""

    operation: str
    success: bool = True
    changed: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    messages: list = field(default_factory=list)
    data: dict = field(default_factory=dict)
    started_at: float = field(default_factory=time.perf_counter)
    duration: float = 0.0
    cancelled: bool = False

    def add(self, level, text, code="", **context):
        message = OperationMessage(
            str(level).lower(), str(text), str(code or ""), dict(context)
        )
        self.messages.append(message)
        if message.level == "error":
            self.success = False
        return message

    def info(self, text, code="", **context):
        return self.add("info", text, code, **context)

    def warning(self, text, code="", **context):
        return self.add("warning", text, code, **context)

    def error(self, text, code="", **context):
        return self.add("error", text, code, **context)

    def complete(self):
        self.duration = max(0.0, time.perf_counter() - self.started_at)
        return self

    @property
    def warnings(self):
        return [message for message in self.messages if message.level == "warning"]

    @property
    def errors(self):
        return [message for message in self.messages if message.level == "error"]

    def as_dict(self):
        return {
            "operation": self.operation,
            "success": bool(self.success),
            "changed": list(self.changed),
            "skipped": list(self.skipped),
            "messages": [message.as_dict() for message in self.messages],
            "data": dict(self.data),
            "duration": float(self.duration),
            "cancelled": bool(self.cancelled),
        }


__all__ = ["OperationMessage", "OperationResult"]
