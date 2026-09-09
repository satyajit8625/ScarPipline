"""Atomic Maya scene transactions used by every modifying ScarTools tool."""

from __future__ import print_function


class SceneTransaction:
    """One undo step with failure rollback and selection restoration.

    A caller should call :meth:`mark_mutating` immediately before invoking a
    Maya command that may partially change the scene.  This deliberate timing
    ensures rollback still runs when Maya mutates and then raises.
    """

    def __init__(
        self,
        name,
        use_undo=True,
        preserve_selection=True,
        suspend_refresh=False,
        suspend_evaluation=False,
        log=None,
    ):
        self.name = str(name)
        self.use_undo = bool(use_undo)
        self.preserve_selection = bool(preserve_selection)
        self.suspend_refresh = bool(suspend_refresh)
        self.suspend_evaluation = bool(suspend_evaluation)
        self.log = log
        self.mutating = False
        self._chunk_open = False
        self._refresh_suspended = False
        self._evaluation_suspended = False
        self._previous_cycle_check = None
        self._selection = []

    @staticmethod
    def _cmds():
        import maya.cmds as cmds
        return cmds

    def _write(self, message):
        if self.log:
            self.log(str(message))

    def __enter__(self):
        try:
            from ..licensing import require_license, verify_session_token
            token = require_license(self.name)
            if not verify_session_token(token):
                raise RuntimeError("Security Tamper Detected: Invalid licensing session seal for '{}'.".format(self.name))
        except RuntimeError:
            raise
        except Exception:
            pass

        cmds = self._cmds()
        if self.preserve_selection:
            self._selection = cmds.ls(selection=True, long=True) or []

        if self.use_undo:
            cmds.undoInfo(openChunk=True, chunkName=self.name)
            self._chunk_open = True
        if self.suspend_refresh:
            try:
                cmds.refresh(suspend=True)
                self._refresh_suspended = True
            except Exception:
                pass
        if self.suspend_evaluation:
            try:
                if hasattr(cmds, "cycleCheck"):
                    self._previous_cycle_check = bool(
                        cmds.cycleCheck(query=True, evaluation=True)
                    )
                    cmds.cycleCheck(evaluation=False)
                    self._evaluation_suspended = True
            except Exception:
                pass
        return self

    def mark_mutating(self):
        """Mark the transaction before the next potentially mutating call."""
        self.mutating = True
        return self

    def _close_chunk(self):
        if self._chunk_open:
            self._cmds().undoInfo(closeChunk=True)
            self._chunk_open = False

    def _restore_environment(self):
        cmds = self._cmds()
        if self._evaluation_suspended:
            try:
                if self._previous_cycle_check is not None and hasattr(cmds, "cycleCheck"):
                    cmds.cycleCheck(evaluation=self._previous_cycle_check)
            except Exception:
                pass
            self._evaluation_suspended = False
        if self._refresh_suspended:
            try:
                cmds.refresh(suspend=False)
                cmds.refresh(force=True)
            except Exception:
                pass
            self._refresh_suspended = False
        if self.preserve_selection:
            try:
                if self._selection:
                    cmds.select(self._selection, replace=True)
                else:
                    cmds.select(clear=True)
            except Exception:
                pass

    def __exit__(self, exc_type, exc_value, traceback):
        close_error = None
        try:
            try:
                self._close_chunk()
            except Exception as error:
                close_error = error
            if (exc_type is not None or close_error is not None) and self.use_undo and self.mutating:
                try:
                    self._cmds().undo()
                    self._write("WARNING: Failed operation was rolled back.")
                except Exception as rollback_error:
                    self._write(
                        "ERROR: Automatic rollback failed: {}".format(rollback_error)
                    )
        finally:
            self._restore_environment()
        if close_error is not None and exc_type is None:
            raise close_error
        return False


__all__ = ["SceneTransaction"]
