"""Character Finalizer controller using the suite-wide operation contract."""

from scartools.framework import ToolController


class CharacterFinalizerController(ToolController):
    def __init__(self, callbacks=None):
        super(CharacterFinalizerController, self).__init__(
            "character_finalizer", callbacks=callbacks
        )


CONTROLLER = CharacterFinalizerController
__all__ = ["CONTROLLER", "CharacterFinalizerController"]
