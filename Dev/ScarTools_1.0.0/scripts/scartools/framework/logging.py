# -*- coding: utf-8 -*-
"""Centralized, real-time logging event bus and store for all ScarTools packages."""

from __future__ import print_function

import collections
import datetime
import logging
import re
import sys
import threading
import time

LOGGER_PREFIX = "scartools"
MAX_LOG_ENTRIES = 1500

LEVEL_INFO = "info"
LEVEL_SUCCESS = "success"
LEVEL_WARNING = "warning"
LEVEL_ERROR = "error"

VALID_LEVELS = (LEVEL_INFO, LEVEL_SUCCESS, LEVEL_WARNING, LEVEL_ERROR)

_ERROR_RE = re.compile(
    r"(?:\bERROR:|\bCRITICAL:|\bEXCEPTION:|\bTRACEBACK|\bFAILED:|\b[1-9][0-9]*\s+ERROR\(S\)|\b[1-9][0-9]*\s+CRITICAL\b|❌)",
    re.IGNORECASE,
)
_WARNING_RE = re.compile(
    r"(?:\bWARNING:|\bWARN:|\bCAUTION:|\bSKIP:|\bSKIPPED:|\bMISSING:|\bBLOCKED:|\bISSUES DETECTED|\b[1-9][0-9]*\s+WARNING\(S\)|⚠️)",
    re.IGNORECASE,
)
_SUCCESS_RE = re.compile(
    r"(?:\bSUCCESS:|\bSUCCESS\b|\bDONE:|\bAPPLIED:|\bCOMPLETE\b|\bHEALTHY\b|\b100% CLEAN\b|\bPASSED\b|✓)",
    re.IGNORECASE,
)


def detect_level(message):
    """Classify plain message text into semantic levels: error, warning, success, or info."""
    text = str(message or "").strip()
    if _ERROR_RE.search(text):
        return LEVEL_ERROR
    if _WARNING_RE.search(text):
        return LEVEL_WARNING
    if _SUCCESS_RE.search(text):
        return LEVEL_SUCCESS
    return LEVEL_INFO


class LogEntry(object):
    """Immutable record of a single log event."""

    __slots__ = ("timestamp", "time_str", "level", "source", "message", "raw_text")

    def __init__(self, message, level=None, source=None, timestamp=None):
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.time_str = datetime.datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")
        self.message = str(message or "").rstrip()
        self.level = level if level in VALID_LEVELS else detect_level(self.message)
        self.source = str(source or "General").strip()
        self.raw_text = "[{}] [{}] [{}] {}".format(
            self.time_str, self.level.upper(), self.source, self.message
        )

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "time_str": self.time_str,
            "level": self.level,
            "source": self.source,
            "message": self.message,
        }

    def __repr__(self):
        return "<LogEntry {} [{}] [{}] {}>".format(
            self.time_str, self.level.upper(), self.source, self.message[:40]
        )


class GlobalLogStore(object):
    """Thread-safe centralized ring-buffer log store with pub/sub event stream."""

    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(GlobalLogStore, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, maxlen=MAX_LOG_ENTRIES):
        if getattr(self, "_initialized", False):
            return
        self._lock = threading.RLock()
        self._entries = collections.deque(maxlen=maxlen)
        self._subscribers = []
        self._counts = {
            "all": 0,
            LEVEL_INFO: 0,
            LEVEL_SUCCESS: 0,
            LEVEL_WARNING: 0,
            LEVEL_ERROR: 0,
        }
        self._sources = set()
        self._initialized = True

    def emit(self, message, level=None, source=None):
        """Append a message to the centralized store and broadcast to listeners."""
        if not message:
            return None
        # Handle multi-line blocks cleanly line by line
        text = str(message).rstrip()
        lines = text.splitlines()
        first_entry = None

        with self._lock:
            for line in lines:
                if not line.strip():
                    continue
                entry = LogEntry(line, level=level, source=source)
                if first_entry is None:
                    first_entry = entry
                self._entries.append(entry)
                self._counts["all"] += 1
                self._counts[entry.level] = self._counts.get(entry.level, 0) + 1
                self._sources.add(entry.source)
                self._notify(entry)

        return first_entry

    def subscribe(self, callback):
        """Register a callable that receives new LogEntry objects as they arrive."""
        with self._lock:
            if callable(callback) and callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback):
        """Remove a previously registered subscriber."""
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def _notify(self, entry):
        for sub in list(self._subscribers):
            try:
                sub(entry)
            except Exception:
                pass

    def get_entries(self, level=None, source=None, query=None):
        """Return filtered list of LogEntry records matching active filter conditions."""
        with self._lock:
            entries = list(self._entries)

        if level and level != "all":
            entries = [e for e in entries if e.level == level]

        if source and source != "all":
            norm_source = source.lower()
            entries = [e for e in entries if norm_source in e.source.lower()]

        if query:
            norm_query = query.strip().lower()
            if norm_query:
                entries = [
                    e for e in entries
                    if norm_query in e.message.lower() or norm_query in e.source.lower()
                ]

        return entries

    def query(self, level=None, source=None, search=None, query=None):
        """Convenience alias for get_entries supporting both search and query keywords."""
        q = search if search is not None else query
        return self.get_entries(level=level, source=source, query=q)

    def get_counts(self, source=None):
        """Return count dictionary for all semantic levels."""
        with self._lock:
            if not source or source == "all":
                return dict(self._counts)
            counts = {"all": 0, LEVEL_INFO: 0, LEVEL_SUCCESS: 0, LEVEL_WARNING: 0, LEVEL_ERROR: 0}
            norm_source = source.lower()
            for e in self._entries:
                if norm_source in e.source.lower():
                    counts["all"] += 1
                    counts[e.level] = counts.get(e.level, 0) + 1
            return counts

    def counts(self, source=None):
        """Convenience alias for get_counts."""
        return self.get_counts(source=source)

    def get_sources(self):
        """Return all distinct source tools that have emitted logs."""
        with self._lock:
            return sorted(list(self._sources))

    def clear(self):
        """Clear all stored logs and reset level counters."""
        with self._lock:
            self._entries.clear()
            self._counts = {
                "all": 0,
                LEVEL_INFO: 0,
                LEVEL_SUCCESS: 0,
                LEVEL_WARNING: 0,
                LEVEL_ERROR: 0,
            }
            self._sources.clear()
            for sub in list(self._subscribers):
                try:
                    sub(None)  # None indicates reset/clear signal
                except Exception:
                    pass


# Suite-wide singleton instance
_GLOBAL_STORE = GlobalLogStore()


def log_store():
    """Return the global log store singleton."""
    return _GLOBAL_STORE


def emit_log(message, level=None, source=None):
    """Emit a message to the centralized ScarTools global log."""
    return _GLOBAL_STORE.emit(message, level=level, source=source)


def get_logger(component):
    """Return a namespaced logger hooked to both Python logging and ScarTools GlobalLogStore."""
    suffix = str(component or "pipeline").strip(". ") or "pipeline"
    name = "{}.{}".format(LOGGER_PREFIX, suffix)
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger
