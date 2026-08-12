# SDL — Phase-1 Implementation v1.1

## Relocatable runtime

SDL contains **no hard-coded E:\NSE_Daily_Analysis\... path**.

By default:
- project root = directory containing `config.py`
- input = `<project>\data\input`
- events = `<project>\data\events`
- state = `<project>\data\state`
- logs = `<project>\logs`

Any of these can be changed at runtime with environment variables.

### Environment variables

```powershell
$env:SDL_PROJECT_ROOT = "D:\Projects\SDL"
$env:SDL_INPUT_DIR = "D:\MarketData\SDL\Input"
$env:SDL_EVENT_DIR = "D:\MarketData\SDL\Events"
$env:SDL_STATE_DIR = "D:\MarketData\SDL\State"
$env:SDL_LOG_DIR = "D:\MarketData\SDL\Logs"
$env:SDL_DASHBOARD_PORT = "8504"
```

Optional:
```powershell
$env:SDL_EVENT_CSV = "D:\MarketData\SDL\Events\breakout_events.csv"
$env:SDL_STATE_JSON = "D:\MarketData\SDL\State\processing_state.json"
```

This means input, output and runtime locations can be changed without editing Python source code.

## PowerShell launcher

```powershell
.\start_sdl_dashboard.ps1 -ProjectRoot "E:\NSE_Daily_Analysis\SDL" -Port 8504
```

Or place the project elsewhere:

```powershell
.\start_sdl_dashboard.ps1 -ProjectRoot "D:\SDL" -Port 8510
```

If the project has its own `.venv`, the launcher uses it. Otherwise it uses the active/system `python`.

## Process a snapshot

The processing command receives the input file path directly:

```powershell
python run_snapshot.py "D:\MarketData\SDL\Input\SDL_Snapshot_2026-08-11_10-00.xlsx"
```

Therefore the source file itself does not need to live in the default input folder.

If the filename has no timestamp:

```powershell
python run_snapshot.py "D:\MarketData\SDL\Input\snapshot.xlsx" --timestamp "2026-08-11 10:00"
```

## Important

The runtime path mechanism is independent of the strategy logic. Changing folders does not change the breakout calculation.

The source/base-premium calculation remains guarded until the exact source formula is verified.
