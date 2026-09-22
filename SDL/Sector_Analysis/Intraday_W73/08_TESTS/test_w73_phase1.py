from pathlib import Path
import sys, json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"02_FEATURE_ENGINE"))
sys.path.insert(0,str(ROOT/"03_LIVE_ADAPTER"))
from w73_universe_engine import evaluate

def test_missing_never_becomes_zero():
    d=evaluate([{"Symbol":"AAA","Close":100,"ATM Straddle Price":10,"ATM Straddle %":1,"OI Chg":None,"OI Chg %":None,"Volume":100,"IV":20,"PCR Chg":1}],
               "2026-09-18T09:33:41",{"version":"T","required_fields":["Symbol","Close","OI Chg"],"max_symbols":50})
    assert d[0].eligible is False

def test_point_in_time_latest():
    from w73_point_in_time_service import latest_as_of
    rows=[{"Symbol":"AAA","_observation_timestamp":"2026-09-18T09:18:09"},{"Symbol":"AAA","_observation_timestamp":"2026-09-18T09:23:20"}]
    out=latest_as_of(rows)
    assert out[0]["_observation_timestamp"]=="2026-09-18T09:23:20"

def test_exact_filename_timestamp():
    from w73_live_ingestor import timestamp_from_name
    assert timestamp_from_name("Daywise_Price_and_OI_Summary_29SEP26_Report_2026-09-18_20260918_091809.xlsx").strftime("%H:%M:%S")=="09:18:09"
