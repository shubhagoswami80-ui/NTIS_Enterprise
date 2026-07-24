
"""
EOD Dashboard Render Context V17
"""

class EODDashboardRenderContextV17:

    def create(self, data=None):

        return {
            "dashboard": "EOD",
            "status": "READY",
            "data_available": data is not None
        }
