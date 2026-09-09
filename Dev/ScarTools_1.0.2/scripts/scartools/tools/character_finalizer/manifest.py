"""Declarative ScarTools manifest for Character Finalizer."""

from scartools.framework import ToolManifest

from scartools.version import VERSION


MANIFEST = ToolManifest(
    tool_id="character_finalizer",
    package="scartools.tools.character_finalizer",
    department="rigging",
    label="Character Finalizer...",
    version=VERSION,
    entry_point="scartools.tools.character_finalizer:show_ui",
    close_entry_point="scartools.tools.character_finalizer.ui:close_all_windows",
    controller_entry_point=(
        "scartools.tools.character_finalizer.controller:CharacterFinalizerController"
    ),
    ui_spec_entry_point="scartools.tools.character_finalizer.ui_spec:UI_SPEC",
    annotation="Preflight, build, repair, and validate final character rig connections.",
    icon_name="tool_character_finalizer.png",
    order=20,
    capabilities=(
        "character.finalize.preflight",
        "character.finalize.apply",
        "rig.space_switch.apply",
        "rig.pole_vector_follow.build",
        "rig.visibility.connect",
    ),
    services=(
        ("character.inspect", "scartools.tools.character_finalizer.api:inspect_character", False),
        ("character.build_plan", "scartools.tools.character_finalizer.api:build_plan", False),
        ("character.finalize", "scartools.tools.character_finalizer.api:finalize_character", True),
    ),
)
