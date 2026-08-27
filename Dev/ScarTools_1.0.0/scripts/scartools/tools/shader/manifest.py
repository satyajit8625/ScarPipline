"""Declarative ScarTools manifest for Shader Tools."""

from scartools.framework import ToolManifest

from scartools.version import VERSION


MANIFEST = ToolManifest(
    tool_id="shader_tools",
    package="scartools.tools.shader",
    department="texturing",
    label="Shader Tools...",
    version=VERSION,
    entry_point="scartools.tools.shader:show_ui",
    close_entry_point="scartools.tools.shader.ui:close_all_windows",
    controller_entry_point="scartools.tools.shader.controller:ShaderController",
    ui_spec_entry_point="scartools.tools.shader.ui_spec:UI_SPEC",
    annotation="Export, inspect, import, and reapply Maya shader packages.",
    icon_name="tool_shader_tools.png",
    order=10,
    capabilities=(
        "shader.export",
        "shader.inspect",
        "shader.import",
        "shader.assign",
    ),
    services=(
        ("shader.export_package", "scartools.tools.shader.api:export_shader_package", False),
        ("shader.inspect_package", "scartools.tools.shader.api:inspect_shader_package", False),
        ("shader.import_package", "scartools.tools.shader.api:import_shader_package", True),
    ),
)
