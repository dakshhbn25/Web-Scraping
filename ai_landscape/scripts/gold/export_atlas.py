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
        "12": {"type": "count-plot", "title": "Account priority", "data": {"field": "account_priority"}},
        "14": {"type": "count-plot", "title": "Swiss presence", "data": {"field": "swiss_region"}},
        "5": {"type": "count-plot", "title": "Company type", "data": {"field": "company_type"}},
        "6": {"type": "count-plot", "title": "Team served", "data": {"field": "team_served"}},
        "7": {"type": "count-plot", "title": "Decision Intelligence fit", "data": {"field": "decision_intelligence_fit"}},
        "8": {"type": "count-plot", "title": "Signal type", "data": {"field": "signal"}},
        "9": {"type": "count-plot", "title": "Evidence quality", "data": {"field": "evidence_quality"}},
        "10": {"type": "count-plot", "title": "Tag check", "data": {"field": "tag_check"}},
    },
    "layouts": {"1": {"type": "list", "name": "Default", "chartIds": ["1", "2", "3", "12", "14", "11", "4", "5", "6", "7", "8", "9", "10"]}},
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
    idx.write_text(html, encoding="utf-8")

if TARGET.exists():
    shutil.rmtree(TARGET)
shutil.copytree(out, TARGET)
shutil.rmtree(work, ignore_errors=True)
shutil.rmtree(src.parent, ignore_errors=True)
size = sum(f.stat().st_size for f in TARGET.rglob("*") if f.is_file()) / 1e6
print(f"exported {len(data)} rows to {TARGET} ({size:.0f} MB)")
