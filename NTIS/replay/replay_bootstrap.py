"""
=========================================================
NTIS Replay Bootstrap
Version : 1.0
Purpose :
    Initialize the Replay Engine
    environment.
=========================================================
"""

from replay_info import ReplayInfo
from replay_healthcheck import ReplayHealthCheck


class ReplayBootstrap:

    @staticmethod
    def initialize(replay_folder):

        print("\nInitializing Replay Engine...\n")

        ReplayInfo.show()

        ReplayHealthCheck.run(replay_folder)

        print("\nReplay Engine initialized successfully.\n")

        return True


if __name__ == "__main__":

    ReplayBootstrap.initialize(".")