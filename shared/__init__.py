#!/usr/bin/env python3
"""
Shared Components Package

This package contains reusable components that prevent duplication of functionality
across the DDD Capture Toolkit. All components follow the DRY (Don't Repeat Yourself)
principle and provide standardised interfaces for common operations.

Available Components:
- progress_display_utils: Progress bars, time formatting, and job progress extraction
"""

from .progress_display_utils import (
    ProgressDisplayUtils,
    create_progress_bar,
    format_time,
    extract_job_progress_info
)

__all__ = [
    'ProgressDisplayUtils',
    'create_progress_bar', 
    'format_time',
    'extract_job_progress_info'
]
