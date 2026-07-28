
"""
EOD Dashboard Log Manager V17
"""

class EODDashboardLogManagerV17:

    def write(self, message):
        return {
            "log": message,
            "status": "RECORDED"
        }
