# -*- coding: utf-8 -*-
"""Data contracts and model definitions for Movable Pivot."""

from __future__ import absolute_import, division, print_function


class PivotPreset(object):
    """Encapsulates a single saved pivot preset state."""

    def __init__(self, name, position, rotation=(0.0, 0.0, 0.0), scale_pivot=None, timestamp=""):
        self.name = str(name).strip()
        self.position = tuple(float(x) for x in position)
        self.rotation = tuple(float(x) for x in rotation)
        self.scale_pivot = tuple(float(x) for x in scale_pivot) if scale_pivot else self.position
        self.timestamp = str(timestamp)

    def to_dict(self):
        return {
            "name": self.name,
            "position": list(self.position),
            "rotation": list(self.rotation),
            "scale_pivot": list(self.scale_pivot),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            return None
        return cls(
            name=data.get("name", "Default"),
            position=data.get("position", (0.0, 0.0, 0.0)),
            rotation=data.get("rotation", (0.0, 0.0, 0.0)),
            scale_pivot=data.get("scale_pivot"),
            timestamp=data.get("timestamp", ""),
        )


class PivotTargetInfo(object):
    """Metadata representing the currently active target transform in Maya."""

    def __init__(self, node="", short_name="", presets=None, current_pos=(0, 0, 0), current_rot=(0, 0, 0)):
        self.node = str(node)
        self.short_name = str(short_name or (node.split("|")[-1] if node else "None"))
        self.presets = list(presets or [])
        self.current_pos = tuple(current_pos)
        self.current_rot = tuple(current_rot)
