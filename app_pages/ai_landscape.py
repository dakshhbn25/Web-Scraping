import json
from pathlib import Path

import streamlit as st

from utils.data import load_ai_landscape

CUSTOMERS_FILE = Path(__file__).resolve().parent.parent / "ai_landscape" / "data" / "silver" / "phamax_customers.json"
MAP_FILE =Path(__file__).resolve().parent.parent / "static" / "ai_landscape" / "index.html"
MAP_URL = "/app/static/ai_landscape/index.html"

st.title("AI landscape", icon=":material/hub:")

items = load_ai_landscape()
if not items:
    st.info("No AI work items found. Build them with ai_landscape/scripts/gold/layout_work_items.py.")
    st.stop()

NO_EVIDENCE = "No AI evidence found"
work = [i for i in items if i["concept"] != NO_EVIDENCE]
companies = {i["company"] for i in items}
concepts = {i["concept"] for i in work}
review_count = sum(i["tag_check"] == "review" for i in work)
tiers = {t: len({i["company"] for i in items if i["relevance"] == t}) for t in ("High", "Medium", "Low", "None")}

st.caption(
    "What every company in our gold data is doing in AI, grouped by concept. "
    "Each item is one thing a company is doing, taken from its sponsor text, agenda sessions, roles or public sources. "
    f"Relevance to Ariya: {tiers['High']} high, {tiers['Medium']} medium, {tiers['Low']} low, {tiers['None']} none. "
    "Companies with no AI evidence found sit together in their own group."
)

with st.container(horizontal=True):
    st.metric("AI work items", len(work), border=True)
    st.metric("Companies", len(companies), border=True)
    st.metric("AI concepts", len(concepts), border=True)
    st.metric(
        "Items to review", review_count, border=True,
        help="Stray points: the wording sits closer to another concept than the one tagged. In the map, open the Tag check chart and click 'review' to see them.",
    )

st.subheader("Concept map")
st.caption(
    "Each dot is one AI work item, coloured by concept, so companies working on the same concept sit together. "
    "Hover a dot for the details, drag to select, and use the charts on the right to filter."
)
st.caption(
    "Each card also carries sales fields built from the gold data: Phamax relationship, account priority (with the rule behind it), "
    "event footprint, key contacts with LinkedIn, sponsor profile, and which Phamax customers work on the same AI concepts."
)
if MAP_FILE.exists():
    with st.container(border=True):
        st.iframe(MAP_URL, height=920)
    customers = json.loads(CUSTOMERS_FILE.read_text(encoding="utf-8")) if CUSTOMERS_FILE.exists() else None
    if customers:
        absent = [c["name"] for c in customers["customers"] if not c["dataset_company"]]
        st.caption(
            f"Phamax customers named publicly ({len(customers['customers'])}): {len(customers['customers']) - len(absent)} appear in these events. "
            f"Not seen at any of them: {', '.join(absent)}. Source: phamax.ch and ariya.ai, checked {customers['checked']}. "
            "A company missing from that list may still be a customer."
        )
else:
    st.warning(
        "The map files are missing from static/ai_landscape. Rebuild them with ai_landscape/scripts/gold/export_atlas.py.",
        icon=":material/warning:",
    )
