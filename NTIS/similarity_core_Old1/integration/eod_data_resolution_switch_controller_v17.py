
"""
NTIS V17 Data Resolution Switch Controller

Controlled migration preparation.
Default behaviour keeps current resolver active.
No config changes.
"""

class EODDataResolutionSwitchControllerV17:

    def __init__(self, use_consolidated=False):
        self.use_consolidated = use_consolidated

    def active_mode(self):
        return {
            "mode": "CONSOLIDATED_CORE" if self.use_consolidated else "CURRENT_RESOLVER",
            "status": "READY"
        }

    def switch_to_consolidated(self):
        self.use_consolidated = True
        return {
            "switch": "ENABLED",
            "mode": "CONSOLIDATED_CORE"
        }

    def rollback(self):
        self.use_consolidated = False
        return {
            "switch": "ROLLED_BACK",
            "mode": "CURRENT_RESOLVER"
        }

    def validate_switch_control(self):
        return {
            "controller": "READY",
            "rollback": "AVAILABLE",
            "default_mode": "CURRENT_RESOLVER"
        }
