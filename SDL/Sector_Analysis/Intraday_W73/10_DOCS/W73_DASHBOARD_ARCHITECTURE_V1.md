# W73 Standalone Dashboard Architecture v1

## Rule

W73 is a separate dashboard/application.

Development:
`http://localhost:9005`

It must not modify or depend on the existing SDL dashboard implementation.

## Single entry point

Only this public integration function is exposed:

`render_intraday_w73_page()`

Existing dashboards can consume W73 through that function.

## Boundary

Existing dashboard
    ↓
12_INTEGRATION/w73_entrypoint.py
    ↓
11_DASHBOARD/w73_dashboard.py
    ↓
W73 internal layers

The existing dashboard must not import:
- source adapter;
- point-in-time cache;
- replay engine;
- V8 feature engine;
- strategy internals.

This keeps lift-and-shift possible.
