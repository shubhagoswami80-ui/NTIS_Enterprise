# NTIS SDL — Sector Analysis

## Purpose
Integrated Sector Analysis page for the existing SDL Breakout Streamlit application.

This is **not** a second application and does **not** require another port.

## Core objective
Detect sector rotation by combining:

1. Sector price/OHLC evidence
2. Breadth / constituent participation
3. OI change
4. PE/CE and PE-CE OI context when supplied
5. PCR change
6. IV change
7. Sector/constituent news
8. International/global news
9. Domestic/India news
10. Alignment/conflict between news and observed market data
11. Intraday setup context
12. Swing setup context

## Files
- `sector_models.py` — data models
- `sector_data_loader.py` — read-only discovery and point-in-time replay selection
- `sector_news_engine.py` — deterministic classification of an existing news feed
- `sector_rotation_engine.py` — rotation evidence aggregation
- `sector_page.py` — Streamlit page renderer
- `__init__.py` — package export

## Data boundary
The loader discovers sector-capable XLSX/XLSM/CSV files below the configured source root. It requires a sector-like column and does not invent sector membership.

Windows filesystem creation time (`st_ctime`) is used as the source snapshot/arrival timestamp. Filename timestamps are ignored.

Replay uses the latest completed snapshot at or before the selected boundary.

## News boundary
The package accepts an existing news provider from the SDL dashboard. It does not silently create a second news provider or fabricate global/domestic news.

The current classification is deterministic keyword analysis. It is intentionally a replaceable evidence layer so a later approved AI/news service can be plugged in without changing the rotation model.

## SDL protection
Do not modify:
- `SDL/app.py`
- SDL scoring / qualification
- breakout logic
- existing Live Queue
- existing Replay engine
- existing state/evidence persistence

The sector package is presentation/analysis only.

## Integration contract
The existing dashboard should:
1. Add an internal navigation option `Sector Analysis`.
2. On selection, call:
   `render_sector_analysis_page(active_source_root(), news_provider=existing_news_adapter)`
3. Keep the existing Home/Decision Board path unchanged.
4. Keep the same Streamlit process/port.
5. Do not duplicate the source workbook or data store.
