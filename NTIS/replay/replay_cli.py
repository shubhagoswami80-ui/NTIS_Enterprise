"""
=========================================================
NTIS Replay CLI
Version : 1.0
Purpose :
    Command-line entry point for the
    Historical Replay Engine.
=========================================================
"""

import argparse

from historical_replay import HistoricalReplay


def build_parser():

    parser = argparse.ArgumentParser(
        description="NTIS Historical Replay Engine"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Historical input CSV file",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output folder",
    )

    parser.add_argument(
        "--strategy",
        default="default",
        help="Replay strategy name",
    )

    return parser


def main():

    parser = build_parser()

    args = parser.parse_args()

    print("=" * 60)
    print("NTIS HISTORICAL REPLAY ENGINE")
    print("=" * 60)

    print(f"Input    : {args.input}")
    print(f"Output   : {args.output}")
    print(f"Strategy : {args.strategy}")

    print("\nLoad your replay strategy and execute:")
    print("HistoricalReplay().run(...)")

    # Strategy loading is intentionally left to the
    # NTIS integration layer.


if __name__ == "__main__":
    main()