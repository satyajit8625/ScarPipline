"""Declarative ScarTools manifest for Modeling & Scene Sanitizer."""

from scartools.framework import ToolManifest
from scartools.version import VERSION

MANIFEST = ToolManifest(
    tool_id="model_sanitizer",
    package="scartools.tools.modeling",
    department="modeling",
    label="Model & Scene Sanitizer...",
    version=VERSION,
    entry_point="scartools.tools.modeling:show_ui",
    close_entry_point="scartools.tools.modeling.ui:close_all_windows",
    controller_entry_point="scartools.tools.modeling.controller:ModelSanitizerController",
    ui_spec_entry_point="scartools.tools.modeling.ui_spec:UI_SPEC",
    annotation="Preflight, inspect, and auto-clean mesh topology, transforms, suffixes, layers, and scene clutter.",
    icon_name="department_modeling.png",
    order=10,
    capabilities=(
        "modeling.inspect",
        "modeling.fix",
        "modeling.select",
        "modeling.clean_scene",
    ),
    services=(
        ("modeling.inspect", "scartools.tools.modeling.api:inspect_model", False),
        ("modeling.fix", "scartools.tools.modeling.api:fix_model_issues", True),
        ("modeling.select_issues", "scartools.tools.modeling.api:select_model_issues", False),
        ("modeling.clean_scene", "scartools.tools.modeling.api:clean_scene_clutter", True),
    ),
)
