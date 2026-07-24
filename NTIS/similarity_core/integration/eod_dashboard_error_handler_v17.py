
"""
EOD Dashboard Error Handler V17
"""

class EODDashboardErrorHandlerV17:

    def handle(self, error):

        return {
            "status": "ERROR",
            "message": str(error)
        }
