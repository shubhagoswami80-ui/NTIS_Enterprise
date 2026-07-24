
"""
EOD Dashboard Gateway V17
"""

class EODDashboardGatewayV17:

    def route(self, module):

        return {
            "dashboard": "EOD",
            "module": module,
            "status": "READY"
        }
