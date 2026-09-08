# -*- coding: utf-8 -*-
"""Subprocess Runner and Batch Job Manager for Standalone Anim Export.

Discovers local mayapy.exe binaries, manages background execution threads,
parses real-time JSON IPC progress, and handles process cancellation cleanly.
"""

from __future__ import absolute_import, division, print_function

import glob
import json
import os
import subprocess
import sys
import threading
import time


def discover_mayapy_interpreters():
    """
    Search for installed Maya Python interpreters (mayapy.exe) on the host machine.
    Returns list of dicts: [{'version': '2023', 'path': 'C:\\...\\mayapy.exe'}, ...]
    """
    results = []
    seen_paths = set()

    # 1. Check MAYA_LOCATION environment variable
    maya_loc = os.environ.get("MAYA_LOCATION")
    if maya_loc and os.path.isdir(maya_loc):
        cand = os.path.join(maya_loc, "bin", "mayapy.exe")
        if os.path.isfile(cand):
            norm = os.path.normpath(cand)
            seen_paths.add(norm.lower())
            results.append({"version": os.path.basename(maya_loc), "path": norm})

    # 2. Check standard Windows Autodesk install paths
    win_paths = glob.glob(r"C:\Program Files\Autodesk\Maya*\bin\mayapy.exe")
    for p in sorted(win_paths, reverse=True):
        norm = os.path.normpath(p)
        if norm.lower() not in seen_paths:
            seen_paths.add(norm.lower())
            # Extract version from parent folder name
            ver_part = norm.split(os.sep)[-3]
            results.append({"version": ver_part, "path": norm})

    # 3. Check current python executable if already inside mayapy
    if "mayapy" in sys.executable.lower():
        norm = os.path.normpath(sys.executable)
        if norm.lower() not in seen_paths:
            seen_paths.add(norm.lower())
            results.insert(0, {"version": "Active Python", "path": norm})

    return results


def get_default_mayapy():
    """Return the preferred or most modern mayapy.exe path, or sys.executable as fallback."""
    found = discover_mayapy_interpreters()
    if found:
        return found[0]["path"]
    return sys.executable


class BackgroundExportJob(object):
    """
    Manages a single background export execution running in mayapy.exe.
    """

    def __init__(
        self,
        scene_path,
        output_dir="",
        version="next",
        format_mode="both",
        start_frame=None,
        end_frame=None,
        handles=0,
        step=1.0,
        camera="auto",
        mayapy_path=None,
        on_progress=None,
        on_log=None,
        on_finished=None,
    ):
        self.scene_path = str(scene_path).replace("\\", "/")
        self.output_dir = str(output_dir or "").replace("\\", "/")
        self.version = str(version or "next")
        self.format_mode = str(format_mode or "both")
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.handles = handles
        self.step = step
        self.camera = camera
        self.mayapy_path = mayapy_path or get_default_mayapy()

        self.on_progress = on_progress
        self.on_log = on_log
        self.on_finished = on_finished

        self.process = None
        self.thread = None
        self._is_cancelled = False
        self._is_running = False
        self.result_data = None
        self.error_message = None

    def start(self):
        """Spawn the background worker thread."""
        if self._is_running:
            return
        self._is_running = True
        self._is_cancelled = False
        self.thread = threading.Thread(target=self._run_worker, name="ExportWorkerThread")
        self.thread.daemon = True
        self.thread.start()

    def cancel(self):
        """Terminate the running subprocess."""
        self._is_cancelled = True
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                time.sleep(0.5)
                if self.process.poll() is None:
                    self.process.kill()
            except Exception:
                pass

    def _run_worker(self):
        worker_script = os.path.join(
            os.path.dirname(__file__),
            "standalone_worker.py",
        ).replace("\\", "/")
        if not os.path.isfile(worker_script):
            pyc_candidate = worker_script + "c"
            if os.path.isfile(pyc_candidate):
                worker_script = pyc_candidate

        # Root scripts folder for sys.path resolution
        scripts_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        ).replace("\\", "/")

        cmd = [
            self.mayapy_path,
            "-u",  # Unbuffered stdout/stderr
            worker_script,
            "--scene", self.scene_path,
            "--format", self.format_mode,
            "--version", self.version,
            "--handles", str(self.handles),
            "--step", str(self.step),
            "--camera", str(self.camera),
        ]

        if self.output_dir:
            cmd.extend(["--output-dir", self.output_dir])
        if self.start_frame is not None:
            cmd.extend(["--start", str(self.start_frame)])
        if self.end_frame is not None:
            cmd.extend(["--end", str(self.end_frame)])

        # Ensure active repository scripts dir is on PYTHONPATH so worker loads active modules
        env = os.environ.copy()
        pythonpath = env.get("PYTHONPATH", "")
        if scripts_dir not in pythonpath:
            env["PYTHONPATH"] = scripts_dir + os.pathsep + pythonpath

        # Windows creation flags to suppress console popups
        creationflags = 0
        if os.name == "nt":
            # CREATE_NO_WINDOW = 0x08000000
            creationflags = 0x08000000

        try:
            if self.on_log:
                self.on_log("Starting background worker: {}".format(self.scene_path))

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                env=env,
                creationflags=creationflags,
            )

            # Stream output
            for raw_line in iter(self.process.stdout.readline, ""):
                if self._is_cancelled:
                    break
                line = raw_line.strip()
                if not line:
                    continue

                # Parse JSON IPC packets
                if line.startswith("{") and line.endswith("}"):
                    try:
                        packet = json.loads(line)
                        msg_type = packet.get("type")
                        if msg_type == "progress":
                            if self.on_progress:
                                self.on_progress(
                                    packet.get("pct", 0),
                                    packet.get("message", ""),
                                    current_item=packet.get("current_item", ""),
                                )
                        elif msg_type == "log":
                            if self.on_log:
                                self.on_log(packet.get("message", ""))
                        elif msg_type == "result":
                            self.result_data = packet
                        elif msg_type == "error":
                            self.error_message = packet.get("message")
                            if self.on_log:
                                self.on_log("ERROR: {}".format(self.error_message))
                        continue
                    except Exception:
                        pass

                # Non-JSON stdout lines
                if self.on_log:
                    self.on_log(line)

            self.process.stdout.close()
            ret_code = self.process.wait()

            if self._is_cancelled:
                self.error_message = "Export job was cancelled by user."
            elif ret_code != 0 and not self.error_message:
                self.error_message = "Worker process exited with error code {}".format(ret_code)

        except Exception as e:
            self.error_message = str(e)
            if self.on_log:
                self.on_log("Execution exception: {}".format(e))
        finally:
            self._is_running = False
            if self.on_finished:
                self.on_finished(self.result_data, self.error_message)


__all__ = [
    "discover_mayapy_interpreters",
    "get_default_mayapy",
    "BackgroundExportJob",
]
