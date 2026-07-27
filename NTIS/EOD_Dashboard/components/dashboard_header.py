"""
NTIS EOD Dashboard Header Component
"""

from datetime import datetime


def render_header():
    print()
    print("Dashboard Status: READY")
    print("Mode: EOD")
    print("Timestamp:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
