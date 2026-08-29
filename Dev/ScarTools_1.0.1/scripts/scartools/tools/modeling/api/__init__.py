"""Public headless API for Modeling & Scene Sanitizer."""

from ..operations import (
    ModelSanitizerError,
    inspect_model_and_scene,
    select_issue_components,
    fix_all_safe_issues,
    fix_make_names_unique,
    fix_add_geo_suffixes,
    fix_add_grp_suffixes,
    fix_shader_suffixes,
    fix_freeze_transforms,
    fix_center_pivots,
    fix_delete_construction_history,
    fix_delete_intermediate_shapes,
    fix_unlock_normals,
    fix_clean_scene_clutter,
)

inspect_model = inspect_model_and_scene
select_model_issues = select_issue_components
fix_model_issues = fix_all_safe_issues
clean_scene_clutter = fix_clean_scene_clutter

__all__ = [
    "ModelSanitizerError",
    "inspect_model_and_scene",
    "inspect_model",
    "select_issue_components",
    "select_model_issues",
    "fix_all_safe_issues",
    "fix_model_issues",
    "clean_scene_clutter",
    "fix_make_names_unique",
    "fix_add_geo_suffixes",
    "fix_add_grp_suffixes",
    "fix_shader_suffixes",
    "fix_freeze_transforms",
    "fix_center_pivots",
    "fix_delete_construction_history",
    "fix_delete_intermediate_shapes",
    "fix_unlock_normals",
    "fix_clean_scene_clutter",
]
