from __future__ import annotations

import html
import json


def lightweight_chart_html(symbol: str, series: list[dict], height: int = 260) -> str:
    """Return an isolated chart popup HTML payload for a dashboard component."""
    safe_symbol = html.escape(symbol)
    data = json.dumps(series, separators=(",", ":"))
    return f"""
<div style='width:100%;height:{int(height)}px;background:#091729;border:1px solid #203653;border-radius:8px;padding:6px'>
  <div style='color:#eef4fb;font:800 12px Inter,Segoe UI,Arial;margin:2px 4px 6px'>{safe_symbol} · PRICE</div>
  <div id='ntis-chart' style='width:100%;height:{max(120,int(height)-28)}px'></div>
</div>
<script src='https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js'></script>
<script>
const el=document.getElementById('ntis-chart');
const chart=LightweightCharts.createChart(el,{{layout:{{background:{{color:'#091729'}},textColor:'#93a6bf'}},grid:{{vertLines:{{color:'#172a43'}},horzLines:{{color:'#172a43'}}}},width:el.clientWidth,height:el.clientHeight}});
const series=chart.addLineSeries({{lineWidth:2}});
series.setData({data});
chart.timeScale().fitContent();
window.addEventListener('resize',()=>chart.applyOptions({{width:el.clientWidth}}));
</script>
"""
