"""Export the AI landscape map as a standalone Embedding Atlas web app into static/ai_landscape/.

Reads ai_landscape/data/gold/ai_landscape.parquet (positions already computed by layout_work_items.py).
The Streamlit page "AI Landscape" shows the result in an iframe.

Run once, offline. Needs Python 3.11+ and the exporter only, WITHOUT Atlas's heavy dependencies
(PyTorch and sentence-transformers are not needed because positions are precomputed):
    pip install --no-deps embedding-atlas
    pip install click duckdb fastapi inquirer platformdirs uvicorn tqdm pandas pyarrow cryptography narwhals websockets litellm
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
GOLD = ROOT / "ai_landscape" / "data" / "gold" / "ai_landscape.parquet"
TARGET = ROOT / "static" / "ai_landscape"

# Default view: dots coloured by concept, plus the charts that answer "who works on what".
STATE = {
    "version": "0.25.0",
    "charts": {
        "1": {"type": "embedding", "title": "AI concept map", "data": {"x": "x", "y": "y", "text": "text", "category": "concept"}},
        "2": {"type": "instances", "title": "Work items"},
        "3": {"type": "count-plot", "title": "AI concept", "data": {"field": "concept"}},
        "4": {"type": "count-plot", "title": "Company", "data": {"field": "company"}},
        "11": {"type": "count-plot", "title": "Relevance to Ariya", "data": {"field": "relevance"}},
        "12": {"type": "count-plot", "title": "Priority", "data": {"field": "account_priority"}},
        "14": {"type": "count-plot", "title": "Location", "data": {"field": "swiss_region"}},
        "5": {"type": "count-plot", "title": "Type", "data": {"field": "company_type"}},
        "6": {"type": "count-plot", "title": "Team served", "data": {"field": "team_served"}},
        "7": {"type": "count-plot", "title": "Decision Intelligence fit", "data": {"field": "decision_intelligence_fit"}},
        "8": {"type": "count-plot", "title": "Signal type", "data": {"field": "signal"}},
        "9": {"type": "count-plot", "title": "Evidence quality", "data": {"field": "evidence_quality"}},
        "10": {"type": "count-plot", "title": "Tag check", "data": {"field": "tag_check"}},
    },
    "layouts": {"1": {"type": "list", "name": "Default", "chartIds": ["1", "2", "3", "12", "14", "11", "4", "5", "6", "7", "8", "9", "10"],
                    "showTable": False}},  # bottom table starts hidden (the side panel is hidden by the ?nopanel switch, see below)
    "layoutOrder": ["1"], "currentLayout": "1",
    # long text columns are written as Markdown so links (LinkedIn, websites) are clickable; source_url renders as a link
    "columnStyles": {
        **{c: {"display": "full", "renderer": "markdown"} for c in ("key_contacts", "warm_paths", "all_sessions", "sponsor_profile", "gold_evidence", "phamax_relationship", "swiss_presence")},
        "source_url": {"display": "full", "renderer": "url"},
        # kept in the data (the map and charts use them) but not shown on the card
        **{c: {"display": "hidden"} for c in ("id", "data_flag", "x", "y", "ticket_signal", "date", "signal")},
    },
}

df = pd.read_parquet(GOLD)
# Atlas search only looks in the text column, so lead each text with its company name: searching "Sanofi" then finds that company
df["text"] = df["company"] + ": " + df["text"]
src = Path(tempfile.mkdtemp(prefix="atlas_src_")) / "ai_landscape.parquet"
df.to_parquet(src, index=False)
work = Path(tempfile.mkdtemp(prefix="atlas_"))
labels = df.groupby("concept").agg(x=("x", "median"), y=("y", "median")).reset_index().rename(columns={"concept": "text"})
labels["level"], labels["priority"] = 0, 10
labels[["x", "y", "text", "level", "priority"]].to_parquet(work / "labels.parquet", index=False)
(work / "meta.json").write_text(json.dumps({"props": {"initialState": STATE}}), encoding="utf-8")

exe = Path(sys.executable).parent / ("embedding-atlas.exe" if sys.platform == "win32" else "embedding-atlas")
out = work / "export"
subprocess.run([str(exe), str(src), "--text", "text", "--x", "x", "--y", "y", "--labels", str(work / "labels.parquet"),
                "--duckdb", "wasm", "--export-metadata", str(work / "meta.json"), "--export-application", str(out)], check=True)

# Atlas adds a FILE_NAME column holding the local path of the source file; drop it.
ds = out / "data" / "dataset.parquet"
data = pd.read_parquet(ds)
data.drop(columns=[c for c in data.columns if c == "FILE_NAME"]).to_parquet(ds, index=False)

# Keep only the modern-browser database engine (the legacy 'mvp' build alone is ~39 MB).
for f in list((out / "assets").glob("duckdb-mvp-*.wasm")) + list((out / "assets").glob("duckdb-browser-mvp.worker-*.js")):
    f.unlink()
for d in (out / "duckdb-wasm").glob("*/wasm_mvp"):
    shutil.rmtree(d)

# links on the cards must open in a new tab, not inside the embedded frame
idx = out / "index.html"
html = idx.read_text(encoding="utf-8")
if "<base " not in html:
    html = html.replace("<head>", '<head><base target="_blank" />', 1)
# With ?nopanel in the address the charts side panel is only hidden, not removed. The Streamlit boxes above the map filter through those charts,
# so they must stay alive (a layout with showCharts=false drops them and the filters stop working).
if "nopanel" not in html:
    hide = ("<script>if(new URLSearchParams(location.search).has('nopanel')){var s=document.createElement('style');"
            "s.textContent='.w-full.h-full.flex.flex-row>.overflow-y-scroll.overflow-x-hidden.h-full,.w-full.h-full.flex.flex-row>.w-2.flex-none{display:none!important}';"
            "document.head.appendChild(s)}</script>")
    html = html.replace("</head>", hide + "</head>", 1)
# Dark by default: Atlas follows the browser's light/dark setting, so tell it the browser prefers dark. The viewer can still switch with the map's own
# light/dark button. (Done here, not in metadata.json, because browsers keep serving a stale cached metadata.json.)
if "atlas-dark-default" not in html:
    dark = ('<script id="atlas-dark-default">(function(){var mm=window.matchMedia.bind(window);'
            'window.matchMedia=function(q){if(/prefers-color-scheme:\\s*dark/.test(q))return{matches:true,media:q,onchange:null,addEventListener:function(){},'
            'removeEventListener:function(){},addListener:function(){},removeListener:function(){},dispatchEvent:function(){return false}};return mm(q)}})()</script>')
    html = html.replace("<head>", "<head>" + dark, 1)
# The card that opens when a dot is clicked is a small scrolling box. Give it an "Expand" button that shows the same content in a large reading view
# filling the map frame (not the browser's full-screen mode, which shows an unremovable 'press Esc to exit' notice). Close with the button, a click outside, or Esc.
CARD_JS = r"""<script id="atlas-card-expand">(function(){
var SEL='.embedding-atlas-root > .p-2.border.shadow-md';
function show(card){
  var content=Array.prototype.find.call(card.children,function(c){return !c.hasAttribute('data-expand')});
  if(!content)return;
  var cs=getComputedStyle(card),host=document.querySelector('.dark')||document.getElementById('app')||document.body;
  var ov=document.createElement('div');
  ov.style.cssText='position:fixed;left:0;top:0;right:0;bottom:0;z-index:2147483647;overflow:auto;padding:24px 12px;box-sizing:border-box;background:rgba(0,0,0,.82)';
  var sheet=document.createElement('div');
  sheet.style.cssText='max-width:900px;margin:0 auto;padding:20px 24px;border-radius:8px;font-size:17px;line-height:1.5;background-color:'+(host.classList.contains('dark')?'#0f172a':'#fff')+';background-image:linear-gradient('+cs.backgroundColor+','+cs.backgroundColor+');color:'+cs.color;
  var x=document.createElement('button');
  x.textContent='✕ Close';
  x.style.cssText='position:sticky;top:0;float:right;margin:-8px -12px 0 0;padding:4px 12px;border-radius:6px;border:1px solid currentColor;background:inherit;color:inherit;cursor:pointer;font:inherit;font-size:14px;z-index:1';
  var copy=content.cloneNode(true);
  sheet.appendChild(x);sheet.appendChild(copy);ov.appendChild(sheet);host.appendChild(ov);
  function close(){document.removeEventListener('keydown',key,true);ov.remove()}
  function key(e){if(e.key==='Escape'){e.stopPropagation();close()}}
  x.onclick=close;ov.onclick=function(e){if(e.target===ov)close()};
  document.addEventListener('keydown',key,true);
}
function enhance(){
  document.querySelectorAll(SEL).forEach(function(card){
    if(card.querySelector(':scope > [data-expand]'))return;
    var b=document.createElement('button');
    b.setAttribute('data-expand','1');b.textContent='⤢ Expand';b.title='Read this card full screen';
    b.style.cssText='position:sticky;top:0;align-self:flex-end;height:22px;margin-bottom:-22px;z-index:2;padding:0 8px;font-size:12px;border-radius:4px;border:1px solid currentColor;background:inherit;color:inherit;cursor:pointer';
    b.onclick=function(e){e.stopPropagation();show(card)};
    card.insertBefore(b,card.firstChild);
  });
}
var t=0;new MutationObserver(function(){if(!t)t=requestAnimationFrame(function(){t=0;enhance()})}).observe(document.documentElement,{childList:true,subtree:true});
})()</script>"""
if "atlas-card-expand" not in html:
    html = html.replace("</head>", CARD_JS + "</head>", 1)
idx.write_text(html, encoding="utf-8")

# Copy over the existing folder instead of deleting it first: if the browser still has a map file open (Windows locks it), a delete would stop half-way and leave the map broken.
shutil.copytree(out, TARGET, dirs_exist_ok=True)
for f in sorted(TARGET.rglob('*'), reverse=True):
    if not (out / f.relative_to(TARGET)).exists():  # files of an older export
        try:
            f.unlink() if f.is_file() else f.rmdir()
        except OSError:
            pass
shutil.rmtree(work, ignore_errors=True)
shutil.rmtree(src.parent, ignore_errors=True)
size = sum(f.stat().st_size for f in TARGET.rglob("*") if f.is_file()) / 1e6
print(f"exported {len(data)} rows to {TARGET} ({size:.0f} MB)")
