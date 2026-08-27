"""Central lifecycle registry for every ScarTools window and child dialog."""

from __future__ import print_function

import weakref


class WindowRegistry:
    """Track all live suite windows without keeping deleted Qt objects alive."""

    def __init__(self):
        self._windows = {}

    def register(self, tool_id, window):
        key = str(tool_id or "scartools")
        bucket = self._windows.setdefault(key, [])
        bucket.append(weakref.ref(window, lambda _ref: self._prune(key)))
        try:
            window.destroyed.connect(lambda *_: self._prune(key))
        except Exception:
            pass
        return window

    def _prune(self, tool_id):
        refs = self._windows.get(tool_id, [])
        refs = [reference for reference in refs if reference() is not None]
        if refs:
            self._windows[tool_id] = refs
        else:
            self._windows.pop(tool_id, None)

    def windows(self, tool_id=None):
        keys = [str(tool_id)] if tool_id is not None else list(self._windows)
        result = []
        for key in keys:
            self._prune(key)
            for reference in self._windows.get(key, []):
                window = reference()
                if window is not None:
                    result.append(window)
        return tuple(result)

    def close(self, tool_id=None):
        closed = 0
        for window in reversed(self.windows(tool_id)):
            try:
                window.close()
                window.deleteLater()
                closed += 1
            except Exception:
                pass
        if tool_id is None:
            self._windows.clear()
        else:
            self._windows.pop(str(tool_id), None)
        return closed


WINDOWS = WindowRegistry()


def register_window(tool_id, window):
    return WINDOWS.register(tool_id, window)


def close_tool_windows(tool_id):
    return WINDOWS.close(tool_id)


def close_all_windows():
    return WINDOWS.close()


__all__ = [
    "WINDOWS",
    "WindowRegistry",
    "close_all_windows",
    "close_tool_windows",
    "register_window",
]
