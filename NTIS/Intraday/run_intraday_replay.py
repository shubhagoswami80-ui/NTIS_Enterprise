"""
=========================================================
NTIS Intraday Replay Runner
Version : 1.1

Purpose:
    Command line runner for historical replay.

Usage:
    python run_intraday_replay.py YYYY-MM-DD

Example:
    python run_intraday_replay.py 2026-07-24

Rules:
    - Uses existing configuration
    - No new config files
    - EOD remains read only
=========================================================
"""

import sys
from pathlib import Path
from datetime import datetime

from intraday_historical_replay_engine import (
    IntradayHistoricalReplayEngine
)

from config_loader import (
    EOD_ROOT,
    PRICE_OI_FOLDER,
    PRICE_OI_PATTERN
)


BASE_OUTPUT = Path(
    r"E:\NSE_Daily_Analysis\Intraday\Output"
)


def get_eod_file(replay_date):

    replay_dt = datetime.strptime(
        replay_date,
        "%Y-%m-%d"
    )

    eod_folder = (
        EOD_ROOT
        /
        str(replay_dt.year)
        /
        replay_dt.strftime("%B")
        /
        PRICE_OI_FOLDER
    )


    files = list(
        eod_folder.glob(
            PRICE_OI_PATTERN
        )
    )


    matching = [
        f for f in files
        if replay_date in f.name
    ]


    if not matching:

        raise FileNotFoundError(
            f"EOD file not found for {replay_date}"
        )


    return matching[0]


def get_intraday_folder(replay_date):

    replay_dt = datetime.strptime(
        replay_date,
        "%Y-%m-%d"
    )


    folder = (
        BASE_OUTPUT
        /
        str(replay_dt.year)
        /
        replay_dt.strftime("%B")
        /
        replay_date
    )


    if not folder.exists():

        raise FileNotFoundError(
            f"Intraday snapshot not found: {folder}"
        )


    return folder


def main():

    if len(sys.argv) < 2:

        print(
            "Usage: python run_intraday_replay.py YYYY-MM-DD"
        )

        return


    replay_date = sys.argv[1]


    intraday_folder = get_intraday_folder(
        replay_date
    )


    eod_file = get_eod_file(
        replay_date
    )


    print("=" * 60)
    print("NTIS INTRADAY REPLAY")
    print("=" * 60)

    print("Replay Date :", replay_date)
    print("Intraday    :", intraday_folder)
    print("EOD File    :", eod_file)
    print("Replay Intelligence: ENRICHED (v2.3)")


    engine = IntradayHistoricalReplayEngine(
        intraday_folder,
        eod_file
    )


    output = engine.run()


    print("=" * 60)
    print("REPLAY COMPLETED")
    print(output)
    print("=" * 60)


if __name__ == "__main__":

    main()