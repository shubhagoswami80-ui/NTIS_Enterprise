
"""
NTIS EOD Dashboard Launcher V17
"""

class EODDashboardLauncherV17:
    PORT = 8503

    def start_command(self):
        return "streamlit run eod_dashboard_app_v17.py --server.port 8503"


if __name__ == "__main__":
    print(EODDashboardLauncherV17().start_command())
