@echo off
setlocal enabledelayedexpansion

title ScarTools - Anim Export Standalone Engine

:: Resolve scripts root
set "SCRIPT_DIR=%~dp0..\scripts"
set "PYTHONPATH=%SCRIPT_DIR%;%PYTHONPATH%"

:: Search for mayapy.exe across standard Autodesk installation locations
set "PYTHON_EXE="

for %%v in (2026 2025 2024 2023 2022) do (
    if not defined PYTHON_EXE (
        if exist "C:\Program Files\Autodesk\Maya%%v\bin\mayapy.exe" (
            set "PYTHON_EXE=C:\Program Files\Autodesk\Maya%%v\bin\mayapy.exe"
        )
    )
)

:: If mayapy not found in standard paths, check MAYA_LOCATION
if not defined PYTHON_EXE (
    if defined MAYA_LOCATION (
        if exist "%MAYA_LOCATION%\bin\mayapy.exe" (
            set "PYTHON_EXE=%MAYA_LOCATION%\bin\mayapy.exe"
        )
    )
)

:: Fallback to python on PATH
if not defined PYTHON_EXE (
    set "PYTHON_EXE=python"
)

echo [ScarTools] Launching Anim Export Standalone...
echo [ScarTools] Python Engine: !PYTHON_EXE!
echo [ScarTools] Script Path: %SCRIPT_DIR%

"!PYTHON_EXE!" -m scartools.tools.anim_io

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ScarTools] Application exited with error code %ERRORLEVEL%.
    pause
)
