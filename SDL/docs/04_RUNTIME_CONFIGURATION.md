# SDL Runtime Configuration

SDL must be relocatable. Production Python files must not contain an absolute machine-specific path.

## Resolution order

For each runtime location:

1. Explicit environment variable, if supplied.
2. Otherwise project-relative default.

Defaults:
- `PROJECT_ROOT` = directory containing `config.py`
- `INPUT_DIR` = `PROJECT_ROOT/data/input`
- `EVENT_DIR` = `PROJECT_ROOT/data/events`
- `STATE_DIR` = `PROJECT_ROOT/data/state`
- `LOG_DIR` = `PROJECT_ROOT/logs`

## Supported variables

| Variable | Purpose |
|---|---|
| `SDL_PROJECT_ROOT` | SDL project root |
| `SDL_INPUT_DIR` | Source/input directory |
| `SDL_EVENT_DIR` | Breakout event directory |
| `SDL_STATE_DIR` | Processing state directory |
| `SDL_LOG_DIR` | Runtime log directory |
| `SDL_EVENT_CSV` | Exact event CSV path |
| `SDL_STATE_JSON` | Exact state JSON path |
| `SDL_DASHBOARD_PORT` | Streamlit port |
| `SDL_BREAKOUT_MULTIPLIER` | Initial threshold multiplier |

## Rule

Changing an input/output/runtime folder must never require changing a Python module.
