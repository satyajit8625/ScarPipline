"""Framework controller for Modeling & Scene Sanitizer."""

from scartools.framework import ToolController
from .operations import inspect_model_and_scene, fix_all_safe_issues


class ModelSanitizerController(ToolController):
    """Coordinates modeling inspections and atomic scene cleanups."""

    def __init__(self):
        super(ModelSanitizerController, self).__init__("model_sanitizer")

    def inspect(self, nodes=None):
        return self.run("modeling.inspect", lambda log: inspect_model_and_scene(nodes))

    def fix_all(self, nodes=None):
        return self.run("modeling.fix", lambda log: fix_all_safe_issues(nodes, log=log))
