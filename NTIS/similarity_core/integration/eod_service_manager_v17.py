
"""
NTIS EOD Service Manager V17
Controls start/stop/restart/refresh lifecycle
"""

class EODServiceManagerV17:

    PORT = 8503

    def start(self):
        return {"service": "EOD", "action": "START", "port": self.PORT}

    def stop(self):
        return {"service": "EOD", "action": "STOP"}

    def restart(self):
        return {"service": "EOD", "action": "RESTART"}

    def refresh(self):
        return {"service": "EOD", "action": "REFRESH"}
