"""Common progress, logging, and cancellation callbacks for pipeline jobs."""

from dataclasses import dataclass


class OperationCancelled(RuntimeError):
    """Raised when a caller-provided cancellation predicate becomes true."""


@dataclass
class OperationCallbacks:
    """UI-neutral feedback bridge reusable in Maya UI, batch, and tests."""

    log_callback: object = None
    progress_callback: object = None
    cancelled_callback: object = None

    def log(self, message):
        if self.log_callback:
            self.log_callback(str(message))

    def progress(self, value, message=""):
        if not self.progress_callback:
            return
        try:
            self.progress_callback(int(value), str(message))
        except TypeError:
            self.progress_callback(int(value))

    def check_cancelled(self):
        if self.cancelled_callback and self.cancelled_callback():
            raise OperationCancelled("ScarTools operation was cancelled.")
        return False
