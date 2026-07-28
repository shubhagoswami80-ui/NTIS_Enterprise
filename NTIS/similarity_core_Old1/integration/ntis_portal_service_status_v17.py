
"""
NTIS Portal Service Status V17
"""

class NTISPortalServiceStatusV17:

    def check(self):
        return {
            "Portal": "READY",
            "Intraday": "READY",
            "EOD": "READY"
        }
