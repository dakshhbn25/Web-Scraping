from pathlib import Path

import streamlit as st

from utils.atlas_filters import filter_groups, map_url
from utils.data import load_ai_landscape

MAP_FILE =Path(__file__).resolve().parent.parent / "static" / "ai_landscape" / "index.html"
MAP_URL = "/app/static/ai_landscape/index.html"
CLOSE_ON_PICK = """<script>
(function () {
  if (document.__closeOnPick) return;
  document.__closeOnPick = true;
  function blurBox() { var a = document.activeElement; if (a && a.getAttribute('role') === 'combobox') a.blur(); }
  function closeSoon() { setTimeout(blurBox, 100); setTimeout(blurBox, 400); }  // twice: the page re-renders and may take the focus back after a pick
  document.addEventListener('click', function (e) { if (e.target.closest('[role="option"]')) closeSoon(); }, true);
  document.addEventListener('keydown', function (e) {
    var a = document.activeElement;
    if (e.key === 'Enter' && a && a.getAttribute('role') === 'combobox') closeSoon();
  }, true);
})();
</script>"""

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
review_count = sum(i["tag_check"] == "review" for i in work)

with st.container(horizontal=True):
    st.metric("AI work items", len(work), border=True)
    st.metric("Companies", len(companies), border=True)
    st.metric("AI concepts", len(concepts), border=True)
    st.metric("Swiss Office", with_swiss, border=True)
    st.metric("Items to review", review_count, border=True)

st.subheader("Concept map")
if MAP_FILE.exists():
    groups = {g["label"]: g for g in filter_groups(items)}
    picked = {}
    company_col, *other_cols = st.columns([5, 3, 3, 3], vertical_alignment="bottom")
    with company_col:
        kind = st.segmented_control("Type", ["All", *groups["Type"]["values"]], default="All") or "All"
        shown = sorted({i["company"] for i in items if kind in ("All", i["company_type"])})  # the type narrows the company list
        picked[groups["Company"]["chart"]] = st.multiselect("Company", shown, placeholder="Search here", select_all=False)
    if kind != "All":
        picked[groups["Type"]["chart"]] = [kind]
    for col, label in zip(other_cols, ("Location", "Priority", "Relevance to Ariya")):
        values = [v for v in groups[label]["values"] if v != "Non-pharma"]  # non-pharma is picked with the Type switch
        picked[groups[label]["chart"]] = col.multiselect(label, values, placeholder="Search here", select_all=False)
    with st.container(border=True):
        st.iframe(map_url(MAP_URL, picked), height=920)
    # A multi-select keeps its list open after a pick. Close it right away (blur the box), so the choice is accepted without clicking elsewhere.
    st.html(CLOSE_ON_PICK, unsafe_allow_javascript=True)
else:
    st.warning(
        "The map files are missing from static/ai_landscape. Rebuild them with ai_landscape/scripts/gold/export_atlas.py.",
        icon=":material/warning:",
    )
