# Movable Pivot - Non-Destructive Rigging Pivot Utility

**ScarTools Rigging Department** | Tool ID: `scartools_movable_pivot` | Version: `1.0.0`

---

## Overview

**Movable Pivot** is a production-grade, non-destructive pivot editing tool designed for Maya riggers, modelers, and animators. It solves the limitations of Maya's default pivot editing workflows by using a matrix-based transformation engine with vertex and hierarchy balance compensation.

> **Core Guarantee**: Changing the pivot position or orientation will **NEVER** shift, deform, or pop the object's geometry in world space. The visual appearance of all vertices remains 100% invariant throughout editing.

---

## Key Features

### 1. Multi-Mode Pivot Positioning
- **Center**: Snaps pivot directly to the bounding box geometric centroid.
- **World Origin**: Snaps pivot to `(0, 0, 0)` without modifying transform translation.
- **Component Centroid**: Moves pivot to the exact arithmetic mean of selected vertices, edge midpoints, or polygon face centers.
- **Object Origin**: Snaps pivot to the transform node's local coordinate origin.

### 2. 3-Axis Bounding Box Matrix Alignment
- Granular Min / Center / Max alignment independently on X, Y, and Z axes.
- Common production alignments in 1-click:
  - **Bottom Center**: `X: Center, Y: Min, Z: Center` (ideal for characters, props, vehicles).
  - **Top Center**: `X: Center, Y: Max, Z: Center` (ideal for hanging fixtures, cables).
  - **Left / Right / Corner Bounds**: Snaps to exact bounding box extremities.

### 3. Surface-Aligned Pivot Orientation
- Non-destructively aligns pivot axes to:
  - **Face Normal**: Primary axis points along polygon normal; secondary axis aligns with tangent.
  - **Edge Tangent**: Aligns primary axis along edge vector.
  - **Target Object**: Matches coordinate orientation of another transform in scene.
- Configurable **Primary Axis** (`+X`, `-X`, `+Y`, `-Y`, `+Z`, `-Z`) and **Secondary Axis** (`+Y`, `-Y`, `+Z`, `-Z`, `+X`, `-X`) with automatic Gram-Schmidt orthonormalization.

### 4. Precision Snapping
- **Snap Position**: Matches world pivot position to reference object.
- **Snap Rotation**: Matches world orientation without moving coordinates.
- **Snap Transform**: Matches full 3D position and orientation.

### 5. Persistent Pivot Bookmarks & Presets
- Save multiple named pivot presets (`Hinge_Left`, `Hinge_Right`, `Wheel_FL`, `Grip_Main`) directly onto DAG nodes.
- Presets persist across Maya scene saves using non-destructive JSON node attributes.
- 1-click **Apply**, **Rename**, and **Delete** capabilities.

### 6. Atomic Reset & Undo Rollback
- **Reset Pivot**: Restores the object's original captured pivot state or geometric center.
- Full 1-step `Ctrl+Z` atomic rollback via `SceneTransaction`.

---

## Production Workflows & Examples

### Example 1: Vehicle Wheel Axle Alignment
1. Select wheel geometry.
2. Under **Position**, click `[Center]` or select rim edge loop and click `[Component]`.
3. Under **Orientation**, choose `Edge Tangent` or select the axle joint as reference object.
4. Click `[Match Orientation]`.
5. Under **Presets**, click `[+ Save Preset]` and name it `Wheel_FL_Axle`.

### Example 2: Door & Trapdoor Hinges
1. Select door mesh.
2. Under **Bounding Box Alignment**, set `X: Min`, `Y: Center`, `Z: Center` (or the hinge side).
3. Click `[Align to Bounding Box]`.
4. Click `[+ Save Preset]` -> `Hinge_Left`.

---

## API & Headless Usage

```python
from scartools.tools.rigging.movable_pivot import (
    move_pivot_to_bbox,
    move_pivot_to_components,
    snap_pivot_to_object,
    save_pivot_preset,
    apply_pivot_preset,
    reset_pivot,
)

# Move pivot of selected mesh to bottom center
move_pivot_to_bbox("pCube1", x="center", y="min", z="center")

# Snap pivot to reference locator
snap_pivot_to_object(target_nodes=["door_geo"], reference_node="hinge_loc", snap_pos=True, snap_rot=True)

# Save preset
save_pivot_preset("door_geo", preset_name="Hinge_Left")
```
