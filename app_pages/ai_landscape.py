from pathlib import Path

import streamlit as st

from utils.data import load_ai_landscape

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
swiss_cos = {i["company"]: i["swiss_region"] for i in items}
with_swiss = sum(r in ("Zug", "Switzerland") for r in swiss_cos.values())
in_zug = sum(r == "Zug" for r in swiss_cos.values())
review_count = sum(i["tag_check"] == "review" for i in work)
tiers = {t: len({i["company"] for i in items if i["relevance"] == t}) for t in ("High", "Medium", "Low", "None")}

st.caption(
    "What every company in our gold data is doing in AI, grouped by concept. "
    "Each item is one thing a company is doing, taken from its sponsor text, agenda sessions, roles or public sources. "
    f"Relevance to Ariya: {tiers['High']} high, {tiers['Medium']} medium, {tiers['Low']} low, {tiers['None']} none."
)

with st.container(horizontal=True):
    st.metric("AI work items", len(work), border=True)
    st.metric("Companies", len(companies), border=True)
    st.metric("AI concepts", len(concepts), border=True)
    st.metric(
        "Swiss Office", with_swiss, border=True,
        help=f"Companies with a headquarters or office in Switzerland ({in_zug} of them in Zug, where Phamax is based). Found by web search, so a company with none listed may still have one.",
    )
    st.metric(
        "Items to review", review_count, border=True,
        help="Stray points: the wording sits closer to another concept than the one tagged. In the map, open the Tag check chart and click 'review' to see them.",
    )

st.subheader("Concept map")
if MAP_FILE.exists():
    with st.container(border=True):
        st.iframe(MAP_URL, height=920)
else:
    st.warning(
        "The map files are missing from static/ai_landscape. Rebuild them with ai_landscape/scripts/gold/export_atlas.py.",
        icon=":material/warning:",
    )
