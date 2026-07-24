
"""
NTIS Dashboard Port Configuration V17
"""

class NTISDashboardPortsV17:

    PORTS = {
        "portal": 8501,
        "intraday": 8502,
        "eod": 8503
    }

    @classmethod
    def get_port(cls, module):
        return cls.PORTS.get(module)
