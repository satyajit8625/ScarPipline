# -*- coding: utf-8 -*-
"""Framework controller managing state and live selection for Movable Pivot."""

from __future__ import absolute_import, division, print_function

import maya.cmds as cmds
from scartools.framework.controller import ToolController
from .pivot_manager import get_presets
from .pivot_math import get_world_pivot_position, get_world_pivot_rotation
from .validation import validate_target_node


class MovablePivotController(ToolController):
    """Coordinates selection tracking, validation, and pivot state."""

    def __init__(self):
        super(MovablePivotController, self).__init__("movable_pivot")
        self.active_node = ""
        self.selected_nodes = []
        self.selected_components = []
        self.available_presets = []

    def refresh_selection(self):
        """Query active selection and update target nodes & presets."""
        sel = cmds.ls(selection=True, long=True) or []
        self.selected_nodes = []
        self.selected_components = []

        for item in sel:
            if "." in item:
                self.selected_components.append(item)
                parent_tf = item.split(".")[0]
                if parent_tf not in self.selected_nodes:
                    self.selected_nodes.append(parent_tf)
            else:
                if cmds.nodeType(item) in ("transform", "joint"):
                    self.selected_nodes.append(item)
                else:
                    parents = cmds.listRelatives(item, parent=True, fullPath=True) or []
                    if parents and parents[0] not in self.selected_nodes:
                        self.selected_nodes.append(parents[0])

        self.active_node = self.selected_nodes[0] if self.selected_nodes else ""
        if self.active_node and cmds.objExists(self.active_node):
            self.available_presets = get_presets(self.active_node)
        else:
            self.available_presets = []

        return self.active_node

    def get_target_display_name(self):
        """Return clean short name of active target object for UI display."""
        if not self.active_node:
            return "No Object Selected"
        short = self.active_node.split("|")[-1]
        count = len(self.selected_nodes)
        if count > 1:
            return "{} (+{} objects)".format(short, count - 1)
        return short
