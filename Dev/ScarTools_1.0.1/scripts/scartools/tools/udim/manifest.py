"""Declarative ScarTools manifest for UDIM Texture Manager."""

from scartools.framework import ToolManifest
from scartools.version import VERSION

MANIFEST = ToolManifest(
    tool_id="udim_manager",
    package="scartools.tools.udim",
    department="texturing",
    label="Generate UDIM",
    version=VERSION,
    entry_point="scartools.tools.udim:run_generate_udim",
    close_entry_point="scartools.tools.udim.ui:close_all_windows",
    controller_entry_point="scartools.tools.udim.controller:UDIMController",
    ui_spec_entry_point="scartools.tools.udim.ui_spec:UI_SPEC",
    annotation="1-Click: Automatically format <UDIM> paths, generate hardware tile previews, and reload Viewport 2.0.",
    icon_name="department_texturing.png",
    order=20,

    capabilities=(
        "udim.scan",
        "udim.preview",
        "udim.convert",
    ),
    services=(
        ("udim.scan", "scartools.tools.udim.operations:scan_udim_textures", False),
        ("udim.generate_previews", "scartools.tools.udim.operations:generate_all_udim_previews", True),
    ),
)
