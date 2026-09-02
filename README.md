# ScarTools 1.0.1 — Official Production Manual

ScarTools is the unified Maya department-tool suite for Autodesk Maya (2023, 2024, 2025, 2026+) on Windows 10/11 x64.
Version 1.0.1 provides a clean, centralized framework: every built-in tool lives inside the `scartools` package and uses the shared UI design system, token palettes, real-time logging, window lifecycles, and atomic scene transactions.

---

## 📖 Complete Documentation Portal
👉 **Open [`ScarTools_Documentation.html`](ScarTools_Documentation.html) in any browser for the complete interactive studio manual and API reference.**

---

## 🛠️ Included Tools by Department

### 1. Modeling
- **Model & Scene Sanitizer**: Full preflight QA (26 rules), automatic viewport component selection, and atomic 1-click safe repair.

### 2. Rigging
- **Movable Pivot**: Non-destructive matrix pivot editing engine for snapping, rotating, bounding-box alignment, and persistent node bookmarks with zero transform popping or geometry drift.
- **Skin Tools**:
  - Symmetry-aware **Mirror Skin Weights** (with component auto-detection and label remapping)
  - **Copy Skin Weights** & **Copy SkinCluster**
  - **Skin Weights Cleanup** (pruning, max influences clamp, unbinding unused joints)
  - Packed multi-mesh **Skin Package Export / Import** (`skin_weights_package.json`)
- **Character Finalizer**: Space-switch SMD preflight, validation, scale normalization, and rig lockdown.

### 3. Texturing & LookDev
- **Shader Tools**: Shader network inspection, texture path validation, lookdev variant management, and cross-department material assignments.
- **Generate UDIM**: 1-Click hardware UV tile mipmap preview generator, GPU cache flusher, and Textured display mode activator (Key 6).

### 4. Animation & Pipeline
- **Anim I/O Suite**: Shot animation packaging, world-space baked FBX/Alembic cameras, deforming character and prop point caches with motion blur velocities, and 1-click downstream scene assembly (`shot_manifest.json`).
- **Pipeline Renamer**: Bulk search/replace, prefix/suffix insertion, sequential numbering, and studio suffix presets.
- **Log Viewer**: Centralized studio event bus capturing real-time diagnostic output, warnings, errors, and successes.
- **Design System Showcase**: Live interactive gallery of all centralized DCC widgets, falloff curves, UDIM matrix grids, and studio themes.

---

## 🎨 Centralized DCC UI Framework (`scartools.ui`)

All tools reuse modular, standardized UI controls from `scartools.ui`:
* **`Vector3Input`**: 3-Axis linked coordinate input with X/Y/Z color badges.
* **`UVTileGrid`**: Interactive $10 \times 10$ matrix grid for UDIMs (`1001`–`1040`).
* **`CurveEditorWidget`**: 2D Bézier curve graph for custom falloff curves.
* **`PathPickerWidget`**: File/directory path picker with native drag-and-drop.
* **`PaletteGrid`**: 16-color studio preset swatch selector.
* **`TokenTagInput`**: Dynamic chip tag container with auto-complete suggestions.
* **`StepWizardWidget`**: Visual 4-stage pipeline progress indicator.
* **`PresetBar` / `PresetManager`**: Persistent JSON user preset management (`~/.scartools/presets/`).
* **Multi-Theme Engine**: 4 Switchable Themes (`Dark Studio`, `Cyber Obsidian`, `Slate Blue`, `Maya Match`).

---

## 🚀 1-Drag Installation

1. Navigate to the network folder `O:\Rnd\Scripts\ScarPipline\Share\ScarTools_1.0.1` or extract the zip archive.
2. Drag `drag_drop_install.py` into any open Maya viewport.
3. Click **INSTALL**.

The installer activates the ScarTools menu and shelf tab immediately without requiring a Maya restart.

---

## 💻 Python API Usage

```python
# 1. Open Interactive Design System Showcase
import scartools.ui
scartools.ui.show_showcase()

# 2. Model Sanitizer Batch QA
from scartools.tools.modeling.api import inspect_model_and_scene, fix_all_safe_issues

issues = inspect_model_and_scene(scope="scene")
print(f"Found {len(issues)} issues.")
fix_all_safe_issues()

# 3. Mirror Skin Weights
from scartools.tools.skin.api import mirror_skin_weights

mirror_skin_weights(
    source_mesh="body_geo",
    target_mesh="body_geo",
    plane="YZ",
    direction="pos_to_neg",
    surface_association="closestPoint",
    influence_association="labelMatch"
)

# 4. Real-Time Benchmark Execution Timer
from scartools.framework.benchmark import ExecutionTimer

with ExecutionTimer(operation_name="Skin Processing", item_count=250):
    # Process geometry or influences
    pass

# 5. Export LookDev Shader Package
from scartools.tools.shader.api import export_shader_package

export_shader_package(
    root_directory="O:/Projects/Pirates/Assets/Ship",
    variant_name="default",
    notes="Approved hero lookdev v002"
)
```

---

*Confidential & Proprietary — ScarFall Studio Pipeline Team*
