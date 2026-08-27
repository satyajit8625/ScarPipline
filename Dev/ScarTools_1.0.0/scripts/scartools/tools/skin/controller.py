"""Skin Tools controller using the suite-wide operation contract."""

from scartools.framework import ToolController


class SkinController(ToolController):
    def __init__(self, callbacks=None):
        super(SkinController, self).__init__("skin", callbacks=callbacks)


CONTROLLER = SkinController
__all__ = ["CONTROLLER", "SkinController"]
