"""
=========================================================
NTIS Replay Exceptions
Version : 1.0
Purpose :
    Custom exceptions for the
    Historical Replay Engine
=========================================================
"""


class ReplayError(Exception):
    """Base Replay Exception."""
    pass


class ReplayConfigurationError(ReplayError):
    """Invalid replay configuration."""
    pass


class ReplayDataError(ReplayError):
    """Historical data error."""
    pass


class ReplayValidationError(ReplayError):
    """Replay validation error."""
    pass


class ReplayStrategyError(ReplayError):
    """Strategy execution error."""
    pass


class ReplayOutputError(ReplayError):
    """Replay output generation error."""
    pass