import csv
import json
import os
import threading
import webbrowser
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

LOG_ROOT = r"D:\My-data\Share_P&L\ytdata"
HOST, PORT = "127.0.0.1", 8765
REFRESH_SECONDS = 15

# Presentation layer only. Collector field names remain unchanged.
VISIBLE_COLUMNS = [
    "ticker", "expiry", "total_ce_volume", "ce_volume_change",
    "total_pe_volume", "pe_volume_change", "total_ce_oi", "ce_oi_change",
    "total_pe_oi", "pe_oi_change", "Bias_%"
]


def snapshot_files():
    result = []
    if not os.path.isdir(LOG_ROOT):
        return result
    for day in os.listdir(LOG_ROOT):
        folder = os.path.join(LOG_ROOT, day)
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if name.startswith("snapshot_") and name.endswith(".csv") and not name.endswith(".tmp"):
                path = os.path.join(folder, name)
                if os.path.isfile(path):
                    result.append(path)
    return sorted(result, key=os.path.getmtime, reverse=True)


def read_snapshot(path):
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path, "r", newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error):
        return []


def snapshot_info():
    files = snapshot_files()
    dates = sorted({os.path.basename(os.path.dirname(p)) for p in files}, reverse=True)
    latest = files[0] if files else None
    snapshots = [
        {
            "date": os.path.basename(os.path.dirname(p)),
            "name": os.path.basename(p),
            "path": p,
            "mtime": os.path.getmtime(p),
        }
        for p in files
    ]
    return latest, dates, snapshots


def selected_snapshot(query):
    latest, dates, snapshots = snapshot_info()
    requested_date = query.get("date", [""])[0]
    requested_name = query.get("snapshot", [""])[0]
    for item in snapshots:
        if (not requested_date or item["date"] == requested_date) and (not requested_name or item["name"] == requested_name):
            return item, dates, snapshots
    if latest:
        return next(item for item in snapshots if item["path"] == latest), dates, snapshots
    return None, dates, snapshots


def json_response(handler, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def page():
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YTF Dashboard</title>
<style>
:root {{font-family:Segoe UI,Arial,sans-serif;color:#172033;background:#eef3f7}}
* {{box-sizing:border-box}} body {{margin:0}} .top {{background:#123c55;color:#fff;padding:18px 28px;display:flex;justify-content:space-between;align-items:center;gap:16px}}
.top h1 {{margin:0;font-size:25px}} .top small {{opacity:.8}} .wrap {{padding:22px;max-width:1700px;margin:auto}}
.panel {{background:#fff;border:1px solid #dce5ec;border-radius:12px;padding:16px;margin-bottom:16px;box-shadow:0 2px 8px #123c5510}}
.controls {{display:grid;grid-template-columns:repeat(5,minmax(150px,1fr));gap:12px}} label {{font-size:12px;font-weight:700;color:#526273;display:block;margin-bottom:5px}}
select,input {{width:100%;padding:10px;border:1px solid #cbd6df;border-radius:7px;background:#fff}} button {{width:100%;padding:10px;border:1px solid #b9c9d5;border-radius:7px;background:#e8f0f5;cursor:pointer}}
.metrics {{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:12px}} .metric {{padding:14px;border-radius:10px;background:#f4f8fb;border:1px solid #dbe7ef}} .metric b {{display:block;font-size:23px;margin-top:5px}}
.status {{font-size:12px;color:#526273}} .table-wrap {{overflow:auto;max-height:65vh}} table {{width:100%;border-collapse:collapse;font-size:13px;white-space:nowrap}} th,td {{padding:10px 12px;border-bottom:1px solid #e1e8ee;text-align:right}} th {{position:sticky;top:0;background:#1d587d;color:#fff;z-index:1}} th:first-child,td:first-child {{text-align:left}} tr:nth-child(even) {{background:#f8fafc}} .positive {{color:#087443;font-weight:700}} .negative {{color:#b42318;font-weight:700}} .neutral {{color:#5b6570}} tr.row-positive {{background:#eefaf2 !important}} tr.row-negative {{background:#fff1f0 !important}} tr.row-neutral {{background:#fafbfd !important}} .empty {{padding:28px;text-align:center;color:#687789}}
@media(max-width:900px) {{.controls,.metrics {{grid-template-columns:repeat(2,minmax(140px,1fr))}} .top {{padding:15px}} .wrap {{padding:12px}}}}
</style></head><body>
<header class="top"><div><h1>YTF Dashboard</h1><small>Filtered snapshot view · auto-refresh every {REFRESH_SECONDS} seconds</small></div><div id="clock"></div></header>
<main class="wrap">
<section class="panel"><div class="controls">
<div><label>Trading date</label><select id="date"></select></div>
<div><label>Collection snapshot</label><select id="snapshot"></select></div>
<div><label>Stock filter</label><input id="ticker" placeholder="All stocks"></div>
<div><label>Expiry filter</label><select id="expiry"><option value="all">All expiries</option></select></div>
<div><label>Bias filter</label><select id="bias"><option value="all">All values</option><option value="positive">Positive</option><option value="negative">Negative</option><option value="zero">Zero</option></select></div>
<div><label>Minimum absolute Bias_%</label><input id="threshold" type="number" min="0" step="0.1" value="0"></div><div><label>&nbsp;</label><button id="reset" type="button">Reset filters</button></div>
</div></section>
<section class="metrics"><div class="metric">Visible rows<b id="rows">—</b></div><div class="metric">Snapshot time<b id="time">—</b></div><div class="metric">Positive Bias_%<b id="positive">—</b></div><div class="metric">Negative Bias_%<b id="negative">—</b></div></section>
<section class="panel"><div class="status" id="status">Loading…</div><div class="table-wrap"><table><thead id="head"></thead><tbody id="body"></tbody></table></div></section>
</main>
<script>
const REFRESH={REFRESH_SECONDS*1000};
let allRows=[], currentMeta={{}};
const $=id=>document.getElementById(id);
const cols={json.dumps(VISIBLE_COLUMNS)};
const changeCols=new Set(['ce_volume_change','pe_volume_change','ce_oi_change','pe_oi_change','Bias_%']);
function num(v){{const n=Number(v);return Number.isFinite(n)?n:null}}
function biasClass(v){{const n=num(v);return n>0?'positive':n<0?'negative':''}}
function render(){{
 const ticker=$('ticker').value.trim().toLowerCase(), expiry=$('expiry').value, mode=$('bias').value, threshold=Math.abs(Number($('threshold').value)||0);
 const rows=allRows.filter(r=>{{const b=num(r['Bias_%'])||0;return (!ticker||String(r.ticker||'').toLowerCase().includes(ticker))&&(expiry==='all'||String(r.expiry||'')===expiry)&&(mode==='all'||(mode==='positive'&&b>0)||(mode==='negative'&&b<0)||(mode==='zero'&&b===0))&&Math.abs(b)>=threshold}});
 $('rows').textContent=rows.length; $('positive').textContent=allRows.filter(r=>(num(r['Bias_%'])||0)>0).length; $('negative').textContent=allRows.filter(r=>(num(r['Bias_%'])||0)<0).length;
 $('head').innerHTML='<tr>'+cols.map(c=>'<th>'+c+'</th>').join('')+'</tr>';
 $('body').innerHTML=rows.length?rows.map(r=>{{const b=num(r['Bias_%'])||0;const rowClass=b>0?'row-positive':b<0?'row-negative':'row-neutral';return '<tr class="'+rowClass+'">'+cols.map(c=>{{let v=r[c]??'';let cls=changeCols.has(c)?biasClass(v):'';return '<td class="'+cls+'">'+String(v).replaceAll('&','&amp;').replaceAll('<','&lt;')+'</td>'}}).join('')+'</tr>'}}).join(''):'<tr><td class="empty" colspan="'+cols.length+'">No rows match the selected filters.</td></tr>';
}}
async function loadMeta(){{const r=await fetch('/api/meta',{{cache:'no-store'}});const d=await r.json();const oldDate=$('date').value,oldSnap=$('snapshot').value;
 $('date').innerHTML=d.dates.map(x=>'<option>'+x+'</option>').join('');if(oldDate&&d.dates.includes(oldDate))$('date').value=oldDate;
 await loadSnapshots(); if(oldSnap)$('snapshot').value=oldSnap;
}}
async function loadSnapshots(){{const date=$('date').value;const r=await fetch('/api/snapshots?date='+encodeURIComponent(date),{{cache:'no-store'}});const d=await r.json();const old=$('snapshot').value;$('snapshot').innerHTML=d.snapshots.map(x=>'<option value="'+x.name+'">'+x.name+'</option>').join('');if(d.snapshots.some(x=>x.name===old))$('snapshot').value=old;await loadData()}}
async function loadData(){{const q='?date='+encodeURIComponent($('date').value)+'&snapshot='+encodeURIComponent($('snapshot').value);const r=await fetch('/api/data'+q,{{cache:'no-store'}});const d=await r.json();allRows=d.rows||[];currentMeta=d; $('time').textContent=d.timestamp||'—';const expiries=[...new Set(allRows.map(r=>r.expiry).filter(Boolean))].sort();const oldExpiry=$('expiry').value;$('expiry').innerHTML='<option value="all">All expiries</option>'+expiries.map(x=>'<option>'+String(x).replaceAll('&','&amp;').replaceAll('<','&lt;')+'</option>').join('');if(expiries.includes(oldExpiry))$('expiry').value=oldExpiry;$('status').textContent='Loaded '+(d.name||'no snapshot')+' · '+(d.rows||[]).length+' source rows · Last page update '+new Date().toLocaleTimeString();render()}}
$('date').addEventListener('change',loadSnapshots);$('snapshot').addEventListener('change',loadData);['ticker','expiry','bias','threshold'].forEach(id=>$(id).addEventListener('input',render));$('reset').addEventListener('click',()=>{{ $('ticker').value='';$('expiry').value='all';$('bias').value='all';$('threshold').value='0';render() }});
async function refresh(){{try{{await loadMeta()}}catch(e){{$('status').textContent='Refresh error: '+e}}$('clock').textContent='Updated '+new Date().toLocaleTimeString()}}
refresh();setInterval(refresh,REFRESH);
</script></body></html>'''.encode('utf-8')


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed=urlparse(self.path)
        if parsed.path in ('/','/index.html'):
            data=page();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
        if parsed.path=='/api/meta':
            _,dates,snaps=snapshot_info();json_response(self,{'dates':dates});return
        if parsed.path=='/api/snapshots':
            date=parse_qs(parsed.query).get('date',[''])[0];_,_,snaps=snapshot_info();items=[{'name':x['name']} for x in snaps if x['date']==date];json_response(self,{'snapshots':items});return
        if parsed.path=='/api/data':
            item,_,_=selected_snapshot(parse_qs(parsed.query));rows=read_snapshot(item['path']) if item else [];ts=''
            if rows: ts=rows[0].get('timestamp','')
            json_response(self,{'name':item['name'] if item else '', 'timestamp':ts, 'rows':rows});return
        self.send_error(404)
    def log_message(self,*args): pass


if __name__=='__main__':
    url=f'http://{HOST}:{PORT}/';print(f'YTF dashboard running at {url}');print('Close this window or press Ctrl+C to stop.')
    threading.Timer(1.0,lambda:webbrowser.open(url)).start();ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
