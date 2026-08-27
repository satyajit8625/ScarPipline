"""Shared controller bridge between tool operations and every ScarTools UI."""

from __future__ import print_function

import inspect
import re

from .operations import OperationCallbacks, OperationCancelled
from .results import OperationResult


class ToolController:
    """Run UI-neutral callables with consistent feedback and results."""

    def __init__(self, tool_id, callbacks=None):
        self.tool_id = str(tool_id)
        self.callbacks = callbacks or OperationCallbacks()

    def run(self, operation_id, function, *args, **kwargs):
        result = OperationResult("{}.{}".format(self.tool_id, operation_id))

        # Enforce studio license authentication before running any operation
        try:
            from ..licensing import is_activated
            if not is_activated():
                result.error(
                    "ScarTools Studio License Authentication Required. "
                    "Please activate your workstation license in the ScarTools menu.",
                    code="unlicensed"
                )
                self.callbacks.log("ERROR: Studio License Authentication Required.")
                return result.complete()
        except Exception:
            pass

        def log_message(message):
            text = str(message)
            upper = text.upper()
            is_error = (
                "ERROR:" in upper
                or "EXCEPTION:" in upper
                or "TRACEBACK" in upper
                or "FAILED:" in upper
                or (bool(re.search(r"\bFAILED\b", upper)) and not bool(re.search(r"\b(?:0|NO|NONE|NOT)\s+FAILED\b", upper)))
                or bool(re.search(r"\b[1-9][0-9]*\s+ERROR\(S\)", upper))
            )
            is_warning = any(
                token in upper for token in ("WARNING:", "WARN:", "CAUTION:", "SKIP:", "MISSING:")
            )
            if is_error:
                result.error(text)
            elif is_warning:
                result.warning(text)
            else:
                result.info(text)
            self.callbacks.log(text)

        def progress(value, message=""):
            self.callbacks.progress(value, message)

        try:
            self.callbacks.check_cancelled()
            try:
                parameters = inspect.signature(function).parameters
            except (TypeError, ValueError):
                parameters = {}
            if "log" in parameters:
                kwargs.setdefault("log", log_message)
            if "progress" in parameters:
                kwargs.setdefault("progress", progress)
            value = function(*args, **kwargs)
            self.callbacks.check_cancelled()
            if isinstance(value, OperationResult):
                return value.complete()
            result.data["value"] = value
            result.info("Operation completed.", code="completed")
        except OperationCancelled as exc:
            result.success = False
            result.cancelled = True
            result.warning(str(exc), code="cancelled")
        except Exception as exc:
            result.error(str(exc), code="exception")
        return result.complete()


__all__ = ["ToolController"]
