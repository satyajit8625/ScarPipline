# -*- coding: utf-8 -*-
"""Controller bridge for UDIM Texture Manager."""

from scartools.framework import ToolController
from .operations import scan_udim_textures, generate_all_udim_previews, convert_selected_to_udim


class UDIMController(ToolController):
    def __init__(self, callbacks=None):
        super(UDIMController, self).__init__("udim_manager", callbacks=callbacks)

    def scan(self, nodes=None):
        return self.run("scan", scan_udim_textures, nodes=nodes)

    def generate_previews(self, file_nodes=None):
        return self.run("generate_previews", generate_all_udim_previews, file_nodes=file_nodes)

    def convert_to_udim(self, file_nodes=None):
        return self.run("convert_to_udim", convert_selected_to_udim, file_nodes=file_nodes)
