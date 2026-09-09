# -*- coding: utf-8 -*-
"""Headless Standalone Worker for Anim Export (Maya Background Engine).

Invoked via mayapy.exe to process Maya scenes headlessly without opening the GUI.
Emits real-time JSON progress lines to stdout for parent process tracking.
"""

from __future__ import absolute_import, division, print_function

import argparse
import json
import os
import sys
import traceback


def emit_ipc(msg_type, **kwargs):
    """Emit a structured JSON packet over stdout followed by immediate flush."""
    payload = {"type": str(msg_type)}
    payload.update(kwargs)
    try:
        sys.stdout.write(json.dumps(payload) + "\n")
        sys.stdout.flush()
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="ScarTools Headless Anim Export Worker")
    parser.add_argument("--scene", required=False, help="Path to target Maya scene file (.ma / .mb)")
    parser.add_argument("--output-dir", required=False, default="", help="Export destination directory")
    parser.add_argument("--version", required=False, default="next", help="Target snapshot version (e.g. next, v001)")
    parser.add_argument("--format", required=False, default="both", choices=["abc", "fbx", "both"], help="Format mode")
    parser.add_argument("--start", required=False, type=int, default=None, help="Start frame override")
    parser.add_argument("--end", required=False, type=int, default=None, help="End frame override")
    parser.add_argument("--handles", required=False, type=int, default=0, help="Frame handles")
    parser.add_argument("--step", required=False, type=float, default=1.0, help="Frame step size")
    parser.add_argument("--camera", required=False, default="auto", help="Camera export option (auto, true, false, or name)")
    parser.add_argument("--job-file", required=False, default="", help="Optional JSON job configuration file")

    args, unknown = parser.parse_known_args()

    job_data = {}
    if args.job_file and os.path.isfile(args.job_file):
        try:
            with open(args.job_file, "r") as f:
                job_data = json.load(f)
        except Exception as e:
            emit_ipc("error", message="Failed to parse job file: {}".format(e))
            sys.exit(1)

    scene_path = job_data.get("scene") or args.scene
    if not scene_path or not os.path.isfile(scene_path):
        emit_ipc("error", message="Valid Maya scene file path is required. Given: '{}'".format(scene_path))
        sys.exit(1)

    output_dir = job_data.get("output_dir") or args.output_dir or ""
    version = job_data.get("version") or args.version or "next"
    fmt_mode = (job_data.get("format") or args.format or "both").lower()
    start_frame = job_data.get("start") if job_data.get("start") is not None else args.start
    end_frame = job_data.get("end") if job_data.get("end") is not None else args.end
    handles = int(job_data.get("handles", args.handles or 0))
    step = float(job_data.get("step", args.step or 1.0))
    cam_opt = str(job_data.get("camera") or args.camera or "auto")

    emit_ipc("status", message="Initializing Maya Standalone engine...", current_item="Engine Init")

    # 1. Initialize Maya Standalone
    try:
        import maya.standalone
        maya.standalone.initialize(name="python")
    except Exception as e:
        emit_ipc("error", message="Failed to initialize maya.standalone: {}".format(e), traceback=traceback.format_exc())
        sys.exit(1)

    import maya.cmds as cmds
    import maya.mel as mel

    # 2. Load necessary export plugins
    for plugin in ("AbcExport", "AbcImport", "fbxmaya"):
        try:
            if not cmds.pluginInfo(plugin, query=True, loaded=True):
                cmds.loadPlugin(plugin, quiet=True)
        except Exception as e:
            emit_ipc("log", message="Plugin load warning ({}): {}".format(plugin, e))

    # 3. Open scene file
    emit_ipc("progress", pct=5, message="Opening Maya scene '{}'...".format(os.path.basename(scene_path)), current_item="Opening Scene")
    try:
        cmds.file(scene_path, open=True, force=True, ignoreVersion=True, prompt=False)
    except Exception as e:
        emit_ipc("error", message="Failed to open Maya scene: {}".format(e), traceback=traceback.format_exc())
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass
        sys.exit(1)

    # 4. Resolve Shot Identity and Timeline
    from scartools.framework.naming import parse_shot_scene_identity
    identity = parse_shot_scene_identity(scene_path)
    shot_name = identity.get("shot_name") or "untitled_shot"

    if not output_dir:
        output_dir = identity.get("export_dir") or os.path.dirname(scene_path)

    # Frame Range
    if start_frame is None or end_frame is None:
        try:
            min_t = cmds.playbackOptions(q=True, minTime=True)
            max_t = cmds.playbackOptions(q=True, maxTime=True)
            if start_frame is None:
                start_frame = int(min_t) if min_t is not None else 1001
            if end_frame is None:
                end_frame = int(max_t) if max_t is not None else 1100
            if start_frame > end_frame:
                start_frame, end_frame = end_frame, start_frame
        except Exception:
            start_frame = 1001 if start_frame is None else start_frame
            end_frame = 1100 if end_frame is None else end_frame

    # FPS
    fps = 24.0
    try:
        current_unit = cmds.currentUnit(query=True, time=True)
        fps_map = {
            "film": 24.0, "pal": 25.0, "ntsc": 30.0,
            "show": 48.0, "palf": 50.0, "ntscf": 60.0,
            "24fps": 24.0, "25fps": 25.0, "30fps": 30.0, "60fps": 60.0,
        }
        fps = fps_map.get(str(current_unit).lower(), 24.0)
    except Exception:
        fps = 24.0

    emit_ipc(
        "log",
        message="Shot: {} | Timeline: {} - {} (FPS: {}) | Target Version: {}".format(
            shot_name, start_frame, end_frame, fps, version
        ),
    )

    # 5. Discover Scene Assets and Camera
    from scartools.tools.anim_io.api.exporter import discover_scene_assets
    from scartools.tools.anim_io.api.camera import find_active_shot_camera

    discovered = discover_scene_assets()
    char_nodes = discovered.get("characters", [])
    prop_nodes = discovered.get("props", [])

    cam_node = None
    export_cam = (cam_opt.lower() not in ("false", "0", "none", "off"))
    if export_cam:
        if cam_opt.lower() in ("auto", "true", "1", "yes"):
            cam_node = find_active_shot_camera(shot_name)
        elif cmds.objExists(cam_opt):
            cam_node = cam_opt

    emit_ipc(
        "progress",
        pct=10,
        message="Discovered {} characters, {} props, camera={}".format(
            len(char_nodes), len(prop_nodes), bool(cam_node)
        ),
        current_item="Assets Discovered",
    )

    # Formats mapping
    geo_fmts = ("abc", "fbx") if fmt_mode == "both" else ((fmt_mode,))

    # Progress callback hook forwarding progress IPC events
    from scartools.framework.operations import OperationCallbacks

    def _on_worker_progress(pct, msg, **kwargs):
        emit_ipc(
            "progress",
            pct=int(pct),
            message=str(msg),
            current=kwargs.get("current"),
            total=kwargs.get("total"),
            current_item=kwargs.get("current_item") or str(msg),
        )

    callbacks = OperationCallbacks(
        progress_callback=_on_worker_progress,
        log_callback=lambda m: emit_ipc("log", message=str(m)),
    )

    # 6. Run Export Pipeline
    from scartools.tools.anim_io.operations import export_shot_package

    try:
        res = export_shot_package(
            output_dir=output_dir,
            shot_name=shot_name,
            start_frame=start_frame,
            end_frame=end_frame,
            fps=fps,
            version=version,
            camera_node=cam_node,
            export_camera=bool(cam_node),
            camera_format="fbx",
            character_nodes=char_nodes,
            character_formats=geo_fmts,
            prop_nodes=prop_nodes,
            prop_formats=geo_fmts,
            handles=handles,
            step=step,
            callbacks=callbacks,
        )

        emit_ipc(
            "result",
            status="success",
            shot_name=shot_name,
            version=res.get("version"),
            target_dir=res.get("target_dir"),
            manifest_path=res.get("manifest_path"),
            characters=res.get("characters_exported"),
            props=res.get("props_exported"),
            camera=bool(res.get("camera")),
            files_count=len(res.get("exported_files", [])),
        )
    except Exception as e:
        emit_ipc("error", message="Export execution failed: {}".format(e), traceback=traceback.format_exc())
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass
        sys.exit(1)

    # 7. Clean uninitialization
    try:
        maya.standalone.uninitialize()
    except Exception:
        pass

    emit_ipc("finished", message="Worker completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
