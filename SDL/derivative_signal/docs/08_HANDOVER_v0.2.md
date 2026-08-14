# Decision Signals Handover v0.2

## User workflow
Start the separate Decision Signals app, select today's date/source, press Process Selected Data, review candidates, then repeat processing when newer data arrives.

## Existing SDL
Leave `SDL/app.py` unchanged.

## Validation gate
Test:
- source discovery
- first processing
- second processing with newer data
- BHARTIARTL OHLC/OI/PE-CE evidence
- JUBLFOOD location/confirmation behavior
- existing Straddle dashboard remains unchanged

## Git
Continue the existing day-end Git backup practice. No intraday push is required.

## Next step
After successful local test, update the master/file-flow/change records with the actual final file paths and observed runtime behavior.
