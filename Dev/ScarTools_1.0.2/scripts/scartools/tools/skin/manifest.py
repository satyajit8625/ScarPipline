"""Declarative ScarTools manifest for Skin Tools."""

from scartools.framework import ToolManifest

from scartools.version import VERSION


MANIFEST = ToolManifest(
    tool_id="skin_tools",
    package="scartools.tools.skin",
    department="rigging",
    label="Skin Tools...",
    version=VERSION,
    entry_point="scartools.tools.skin:show_ui",
    close_entry_point="scartools.tools.skin.ui:close_all_windows",
    controller_entry_point="scartools.tools.skin.controller:SkinController",
    ui_spec_entry_point="scartools.tools.skin.ui_spec:UI_SPEC",
    annotation="Import, export, copy, mirror, and clean skin weights.",
    icon_name="tool_skin_tools.png",
    order=10,
    capabilities=(
        "skin.export",
        "skin.package",
        "skin.import",
        "skin.copy_weights",
        "skin.copy_cluster",
        "skin.mirror",
        "skin.cleanup",
        "skin.unbind",
    ),
    services=(
        ("skin.export_package", "scartools.tools.skin.api:export_skin_package", False),
        ("skin.import_package", "scartools.tools.skin.api:import_skin_package", True),
        ("skin.copy_weights", "scartools.tools.skin.api:copy_skin_weights", True),
        ("skin.copy_cluster", "scartools.tools.skin.api:copy_skin_cluster", True),
        ("skin.unbind", "scartools.tools.skin.api:unbind_target_skin_clusters", True),
        ("skin.mirror", "scartools.tools.skin.api:mirror_skin_weights", True),
        ("skin.cleanup", "scartools.tools.skin.api:remove_unused_influences", True),
    ),
)
