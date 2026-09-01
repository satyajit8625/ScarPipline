"""Reusable SDK primitives for every ScarTools department tool."""

from .imports import entry_point_module, load_entry_point
from .logging import get_logger
from .manifest import ToolManifest
from .operations import OperationCallbacks, OperationCancelled
from .controller import ToolController
from .lifecycle import (
    WINDOWS,
    close_all_windows,
    close_tool_windows,
    register_window,
)
from .results import OperationMessage, OperationResult
from .services import SERVICES, ServiceDefinition, ServiceRegistry
from .transactions import SceneTransaction
from .validation import (
    ValidationIssue,
    ValidationReport,
    inspect_mesh_topology,
    select_mesh_topology_issues,
)
from .paths import icons_root, package_root, scripts_root, resolve_icon, open_in_file_manager, is_valid_filename
from .snapshots import (
    SnapshotError,
    asset_directory,
    asset_key,
    current_asset_key,
    current_scene_metadata,
    latest_version,
    reserve_next_version,
    resolve_import_version,
    validate_scene_identity,
)
from .scene import (
    get_selected_transforms,
    get_all_scene_meshes,
    get_shape_node,
    get_short_name,
    split_namespace,
    get_connected_nodes,
    get_scene_fps,
    get_scene_frame_range,
)
from .preflight import (
    PreflightSeverity,
    PreflightStatus,
    PreflightIssue,
    PreflightCheck,
    PreflightReport,
)
from .naming import (
    SuffixRegistry,
    sanitize_maya_name,
    apply_affixes,
    split_version_string,
    format_version,
    parse_shot_scene_identity,
)

__all__ = [
    "ToolManifest",
    "OperationCallbacks",
    "OperationCancelled",
    "OperationMessage",
    "OperationResult",
    "SceneTransaction",
    "ToolController",
    "ValidationIssue",
    "ValidationReport",
    "inspect_mesh_topology",
    "select_mesh_topology_issues",
    "ServiceDefinition",
    "ServiceRegistry",
    "SERVICES",
    "WINDOWS",
    "register_window",
    "close_tool_windows",
    "close_all_windows",
    "load_entry_point",
    "entry_point_module",
    "get_logger",
    "package_root",
    "scripts_root",
    "icons_root",
    "resolve_icon",
    "SnapshotError",
    "asset_directory",
    "asset_key",
    "current_asset_key",
    "current_scene_metadata",
    "latest_version",
    "reserve_next_version",
    "resolve_import_version",
    "validate_scene_identity",
    "get_selected_transforms",
    "get_all_scene_meshes",
    "get_shape_node",
    "get_short_name",
    "split_namespace",
    "get_connected_nodes",
    "PreflightSeverity",
    "PreflightStatus",
    "PreflightIssue",
    "PreflightCheck",
    "PreflightReport",
    "SuffixRegistry",
    "sanitize_maya_name",
    "apply_affixes",
    "split_version_string",
    "format_version",
    "parse_shot_scene_identity",
    "open_in_file_manager",
    "is_valid_filename",
    "get_scene_fps",
    "get_scene_frame_range",
]
