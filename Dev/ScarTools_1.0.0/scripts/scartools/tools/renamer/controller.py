# -*- coding: utf-8 -*-
"""Controller bridge for Pipeline Renamer."""

from scartools.framework import ToolController
from .operations import preview_rename, execute_batch_rename


class RenamerController(ToolController):
    def __init__(self, callbacks=None):
        super(RenamerController, self).__init__("pipeline_renamer", callbacks=callbacks)

    def preview(self, nodes, mode_or_options="unified", options=None):
        return self.run("preview", preview_rename, nodes=nodes, mode_or_options=mode_or_options, options=options)

    def execute_rename(self, nodes, mode_or_options="unified", options=None):
        return self.run("execute_rename", execute_batch_rename, nodes=nodes, mode_or_options=mode_or_options, options=options)
