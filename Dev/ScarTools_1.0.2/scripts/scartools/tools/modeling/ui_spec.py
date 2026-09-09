"""Declarative UI specification for Modeling & Scene Sanitizer."""

UI_SPEC = {
    "tool_id": "model_sanitizer",
    "window_title": "Model & Scene Sanitizer",
    "header_title": "MODEL & SCENE SANITIZER",
    "header_subtitle": "Preflight QA, topology, transforms, suffixes, and layer sanitization",
    "tabs": [
        {"id": "all", "label": "All Checks"},
        {"id": "critical", "label": "Critical (🔴)"},
        {"id": "warnings", "label": "Warnings (🟠)"},
        {"id": "topology", "label": "Topology"},
        {"id": "naming", "label": "Naming"},
        {"id": "transforms", "label": "Transforms"},
        {"id": "shading", "label": "Shading"},
        {"id": "scene", "label": "Scene"},
    ],
}
