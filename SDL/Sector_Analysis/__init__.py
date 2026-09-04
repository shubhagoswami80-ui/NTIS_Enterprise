"""NTIS SDL Sector Analysis.

Isolated analytical package for the existing SDL Breakout Streamlit application.
This package does not modify SDL scoring, qualification, breakout, replay, or state.
"""
from .sector_page import render_sector_analysis_page

__all__ = ["render_sector_analysis_page"]
