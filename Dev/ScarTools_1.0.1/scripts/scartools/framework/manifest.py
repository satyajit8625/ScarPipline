"""Declarative tool contract used throughout the ScarTools suite."""

from __future__ import print_function

import sys
from dataclasses import dataclass, field

from .imports import entry_point_module, load_entry_point


@dataclass(frozen=True)
class ToolManifest:
    """Serializable identity and lifecycle declaration for one Maya tool."""

    tool_id: str
    package: str
    department: str
    label: str
    version: str
    entry_point: str
    annotation: str = ""
    icon_name: str = ""
    order: int = 100
    min_maya_version: int = 2023
    capabilities: tuple = field(default_factory=tuple)
    close_entry_point: str = ""
    controller_entry_point: str = ""
    ui_spec_entry_point: str = ""
    services: tuple = field(default_factory=tuple)

    def __post_init__(self):
        required = {
            "tool_id": self.tool_id,
            "package": self.package,
            "department": self.department,
            "label": self.label,
            "version": self.version,
            "entry_point": self.entry_point,
        }
        for field_name, value in required.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError("ToolManifest.{} cannot be empty.".format(field_name))
        entry_point_module(self.entry_point)
        if self.close_entry_point:
            entry_point_module(self.close_entry_point)
        if self.controller_entry_point:
            entry_point_module(self.controller_entry_point)
        if self.ui_spec_entry_point:
            entry_point_module(self.ui_spec_entry_point)
        if int(self.min_maya_version) < 2023:
            raise ValueError("ScarTools manifests must target Maya 2023 or newer.")
        object.__setattr__(self, "order", int(self.order))
        object.__setattr__(self, "min_maya_version", int(self.min_maya_version))
        object.__setattr__(self, "capabilities", tuple(self.capabilities or ()))
        object.__setattr__(self, "services", tuple(self.services or ()))
        for service in self.services:
            if not isinstance(service, (tuple, list)) or len(service) not in (2, 3):
                raise ValueError(
                    "Manifest services must be (id, entry_point[, mutates_scene])."
                )
            entry_point_module(service[1])

    def launch(self, *args, **kwargs):
        """Load the UI or command only when the artist invokes the menu item."""
        return load_entry_point(self.entry_point)(*args, **kwargs)

    def menu_command(self, *_):
        """Maya menu adapter that ignores Maya's optional callback argument."""
        return self.launch()

    def close_if_loaded(self):
        """Close the tool without importing an unused Qt module."""
        if not self.close_entry_point:
            return False
        module_name = entry_point_module(self.close_entry_point)
        if module_name not in sys.modules:
            return False
        load_entry_point(self.close_entry_point)()
        return True

    def as_dict(self):
        """Return JSON-safe metadata for launchers, diagnostics, or catalogs."""
        return {
            "tool_id": self.tool_id,
            "package": self.package,
            "department": self.department,
            "label": self.label,
            "version": self.version,
            "entry_point": self.entry_point,
            "annotation": self.annotation,
            "icon_name": self.icon_name,
            "order": self.order,
            "min_maya_version": self.min_maya_version,
            "capabilities": list(self.capabilities),
            "close_entry_point": self.close_entry_point,
            "controller_entry_point": self.controller_entry_point,
            "ui_spec_entry_point": self.ui_spec_entry_point,
            "services": [list(service) for service in self.services],
        }
