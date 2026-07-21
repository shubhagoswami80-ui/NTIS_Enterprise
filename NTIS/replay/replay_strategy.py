"""
=========================================================
NTIS Replay Strategy Interface
Version : 1.0
Purpose :
    Base Strategy Interface for
    Historical Replay Engine
=========================================================
"""

from abc import ABC, abstractmethod


class ReplayStrategy(ABC):
    """
    Base class for all replay strategies.
    """

    @abstractmethod
    def evaluate(self, row):
        """
        Evaluate one historical record.

        Parameters
        ----------
        row : pandas.Series

        Returns
        -------
        dict
            Replay result.
        """
        raise NotImplementedError