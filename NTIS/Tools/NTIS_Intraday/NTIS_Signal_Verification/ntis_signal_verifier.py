from pathlib import Path
import json
import time

from analyzers.signal_path import SignalPathAnalyzer
from analyzers.repository import RepositoryUsageAnalyzer
from analyzers.execution import ExecutionChainAnalyzer
from analyzers.probability import ProbabilityAnalyzer
from analyzers.dashboard import DashboardAnalyzer

from generators.signal_audit_generator import SignalAuditGenerator


ROOT = Path(__file__).parent

CONFIG_FILE = ROOT / "config" / "verification_rules.json"

OUTPUT = ROOT / "output"


class NTISSignalVerifier:

    def __init__(self):

        with CONFIG_FILE.open(
            "r",
            encoding="utf-8"
        ) as f:

            self.config = json.load(f)

        OUTPUT.mkdir(
            parents=True,
            exist_ok=True
        )

    def run(self):

        start = time.time()

        print()
        print("=" * 70)
        print(" NTIS SIGNAL VERIFICATION ")
        print("=" * 70)
        print()

        SignalPathAnalyzer(
            self.config,
            OUTPUT
        ).run()

        RepositoryUsageAnalyzer(
            self.config,
            OUTPUT
        ).run()

        ExecutionChainAnalyzer(
            self.config,
            OUTPUT
        ).run()

        ProbabilityAnalyzer(
            self.config,
            OUTPUT
        ).run()

        DashboardAnalyzer(
            self.config,
            OUTPUT
        ).run()

        SignalAuditGenerator(
            OUTPUT
        ).generate()

        print()

        print("=" * 70)

        print("Verification Completed")

        print(f"Elapsed : {round(time.time()-start,2)} sec")

        print("=" * 70)

        print()

        print("Reports")

        for f in sorted(OUTPUT.iterdir()):

            print(f"  {f.name}")

        print()


if __name__ == "__main__":

    NTISSignalVerifier().run()