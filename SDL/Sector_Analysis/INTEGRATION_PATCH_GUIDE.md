# Controlled Integration Guide

This deployment intentionally isolates Sector Analysis from the frozen SDL/V34 dashboard logic.

## Required integration
The existing `SDL/sdl_decision_centre_preview.py` must expose an internal page/navigation state and call:

```python
from Sector_Analysis.sector_page import render_sector_analysis_page
```

Then, inside the existing page router:

```python
elif page == "Sector Analysis":
    render_sector_analysis_page(
        active_source_root(),
        news_provider=existing_news_provider,
    )
```

`existing_news_provider` should adapt the already-used SDL news feed into:

```python
[
    {
        "title": "...",
        "timestamp": "...",
        "source": "...",
    },
]
```

Do not add a duplicate news provider merely for Sector Analysis.

## Navigation requirement
Use the existing Streamlit application and port. Do not create another launcher or another dashboard.

## Home requirement
No Home-page market-focus/conclusion card is included in this deployment. That is deliberately deferred until the sector-rotation evidence has been reviewed.

## Protected areas
Do not modify SDL scoring, qualification, breakout, Live Queue, existing Replay, or Historical Evidence.
