"""Filter search for the AI landscape map.

The Embedding Atlas page keeps its whole state, including which values are ticked in each chart, in the URL hash
(#?state=<raw-deflate JSON, base64url>). This module lists the values of the few filters we expose (company, location,
priority, relevance to Ariya) and builds the map URL with the chosen ones already ticked, so Streamlit drop-downs
above the iframe can drive the map's side-panel filters.
"""
import base64
import json
import zlib
from pathlib import Path

META = Path(__file__).resolve().parent.parent / "static" / "ai_landscape" / "data" / "metadata.json"

# (label shown above the drop-down, data field of the map chart, fixed value order or None for A-Z)
FILTERS = [
    ("Company", "company", None),
    ("Location", "swiss_region", ["Zug", "Switzerland", "Elsewhere", "Not verified"]),
    ("Type", "company_type", ["Pharma", "Non-pharma"]),  # shown inside the Company column
    ("Priority", "account_priority", None),  # includes "Non-pharma": those companies get no letter
    ("Relevance to Ariya", "relevance", ["High", "Medium", "Low", "None"]),
]


def _state() -> dict:
    return json.loads(META.read_text(encoding="utf-8"))["props"]["initialState"]


def filter_groups(items: list[dict]) -> list[dict]:
    """[{label, chart (map chart id), values}] for each exposed filter, values read from the data."""
    chart_of = {c["data"]["field"]: cid for cid, c in _state()["charts"].items() if c.get("type") == "count-plot"}
    groups = []
    for label, field, order in FILTERS:
        present = {str(i[field]) for i in items if i.get(field) not in (None, "")}
        values = [v for v in order if v in present] + sorted(present - set(order)) if order else sorted(present)
        groups.append({"label": label, "chart": chart_of[field], "values": values})
    return groups


def map_url(base_url: str, picked: dict[str, list[str]]) -> str:
    """The map URL with `picked` ({chart id: [values]}) ticked. Values of one chart are OR-ed, different charts AND-ed (Atlas behaviour).
    ?nopanel hides the charts side panel (they keep working; see export_atlas.py). The ?v= part makes the browser reload the map:
    a change of the #hash alone would not."""
    picked = {cid: vals for cid, vals in picked.items() if vals}
    state = _state()  # always sent in the link, so the map never falls back to a stale browser-cached metadata.json
    if picked:
        state["chartStates"] = {cid: {"selection": vals} for cid, vals in picked.items()}
    packer = zlib.compressobj(wbits=-15)  # raw deflate, as Atlas expects
    packed = packer.compress(json.dumps(state, separators=(",", ":")).encode("utf-8")) + packer.flush()
    token = base64.urlsafe_b64encode(packed).decode().rstrip("=")
    return f"{base_url}?nopanel&v={zlib.crc32(token.encode())}#?state={token}"
