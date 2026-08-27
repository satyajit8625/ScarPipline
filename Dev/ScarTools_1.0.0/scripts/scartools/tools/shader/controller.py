"""Shader Tools controller using the suite-wide operation contract."""

from scartools.framework import ToolController


class ShaderController(ToolController):
    def __init__(self, callbacks=None):
        super(ShaderController, self).__init__("shader", callbacks=callbacks)


CONTROLLER = ShaderController
__all__ = ["CONTROLLER", "ShaderController"]
