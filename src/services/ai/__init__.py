"""AI Service package exporting all split modules."""
from __future__ import annotations

from .client import check_health
from .vision import analyze_image
from .audio import transcribe_audio
from .analysis import (
    describe_dataset,
    describe_result,
    suggest,
    generate_code,
    generate_corrected_code,
    plan_next_step,
    interpret,
    analyze_image_for_data,
    fallback_suggestions,
)
from .forms import generate_form_schema
from .reports import arrange_report, edit_report_with_ai

__all__ = [
    "check_health",
    "analyze_image",
    "transcribe_audio",
    "describe_dataset",
    "describe_result",
    "suggest",
    "generate_code",
    "generate_corrected_code",
    "plan_next_step",
    "interpret",
    "analyze_image_for_data",
    "fallback_suggestions",
    "generate_form_schema",
    "arrange_report",
    "edit_report_with_ai",
]
