"""
Web UI module for Agent Inspector.

Provides a simple, responsive web interface with three-panel layout:
- Left Panel (30%): Run list with filters and search
- Center Panel (45%): Timeline visualization
- Right Panel (25%): Detail view for selected events
"""

from .app import get_index_html, setup_ui, ui_router

__all__ = [
    "ui_router",
    "setup_ui",
    "get_index_html",
]
