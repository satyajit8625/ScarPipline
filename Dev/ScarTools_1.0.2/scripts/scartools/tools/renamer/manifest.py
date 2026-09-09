"""Declarative ScarTools manifest for Pipeline Renamer."""

from scartools.framework import ToolManifest
from scartools.version import VERSION

MANIFEST = ToolManifest(
    tool_id="pipeline_renamer",
    package="scartools.tools.renamer",
    department="pipeline_utilities",
    label="Pipeline Renamer...",
    version=VERSION,
    entry_point="scartools.tools.renamer:show_ui",
    close_entry_point="scartools.tools.renamer.ui:close_all_windows",
    controller_entry_point="scartools.tools.renamer.controller:RenamerController",
    ui_spec_entry_point="scartools.tools.renamer.ui_spec:UI_SPEC",
    annotation="Fast batch node renaming with search/replace, numbering, and department suffix presets.",
    icon_name="department_pipeline.png",
    order=10,
    capabilities=(
        "renamer.rename",
        "renamer.search_replace",
        "renamer.presets",
    ),
    services=(
        ("renamer.batch_rename", "scartools.tools.renamer.operations:execute_batch_rename", True),
    ),
)
