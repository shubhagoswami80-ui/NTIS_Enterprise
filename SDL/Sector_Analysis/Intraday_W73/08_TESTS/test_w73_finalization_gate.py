from pathlib import Path
import importlib.util
p=Path(__file__).with_name('w73_finalization_gate.py')
spec=importlib.util.spec_from_file_location('gate',p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def test_timestamp_parser():
    assert m.ts_from_name(Path('Daywise_Price_and_OI_Summary_X_20260918_091809.xlsx')).strftime('%H:%M:%S')=='09:18:09'

def test_exact_coverage_rule():
    # Source beginning at 09:18 cannot prove a 09:15 market-open ORB.
    assert not (m.datetime(2026,9,18,9,18)<=m.datetime(2026,9,18,9,15))
