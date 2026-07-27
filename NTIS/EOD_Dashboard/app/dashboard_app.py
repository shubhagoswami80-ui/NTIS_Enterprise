"""
NTIS EOD Dashboard Main Application
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from EOD_Dashboard.pages.market_overview import show_market_overview


def run_dashboard():

    print("=" * 60)
    print("NTIS EOD INTELLIGENCE DASHBOARD")
    print("=" * 60)

    show_market_overview()


if __name__ == "__main__":
    run_dashboard()
