# W73 Single Entry Point

The integration boundary is intentionally one function:

```python
from w73_entrypoint import render_intraday_w73_page
render_intraday_w73_page()
```

Existing dashboards should consume this entry point rather than importing
W73 internal engines, cache modules, replay modules, or source adapters.

Development dashboard:
- standalone
- port 9005
- no dependency on the existing SDL dashboard

Future merge:
- existing dashboard imports only `render_intraday_w73_page`
- W73 remains independently testable and deployable
