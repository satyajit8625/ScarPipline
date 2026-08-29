# -*- coding: utf-8 -*-
"""Declarative UI specification for Pipeline Renamer."""

from scartools.framework import UISpecification

UI_SPEC = UISpecification(
    title="PIPELINE RENAMER",
    subtitle="Fast batch node renaming with search/replace, numbering, and department suffix presets",
    accent="pipeline",
    actions=(
        ("APPLY BATCH RENAME", "primary"),
    ),
)
