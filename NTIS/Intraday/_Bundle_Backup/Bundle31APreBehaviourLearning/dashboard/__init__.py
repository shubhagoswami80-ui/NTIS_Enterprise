"""
NTIS Intraday Dashboard Package

This package contains the presentation layer for the NTIS Intraday
Dashboard.

Design Principles
-----------------
- UI components are separated from the dashboard entry point.
- Business logic remains outside this package.
- Data loading is handled by dashboard_loader.
- Sidebar controls are handled by dashboard_sidebar.
- Remaining UI sections are added incrementally in subsequent bundles.

This module intentionally contains no executable logic.
"""

from .dashboard_loader import (
    resolve_snapshot,
    load_dashboard_data,
)

from .dashboard_sidebar import (
    build_sidebar_filters,
)

__all__ = [
    "resolve_snapshot",
    "load_dashboard_data",
    "build_sidebar_filters",
]