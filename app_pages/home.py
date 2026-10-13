import streamlit as st

from utils.data import (
    events,
    load_agenda,
    load_agenda_speakers,
    load_ai_landscape,
    load_speakers,
    load_sponsors,
    load_tickets,
    unique_speakers,
)

st.title("Overview", icon=":material/home:")

speaker_appearances = load_speakers()
speakers_list = unique_speakers(speaker_appearances)  # one row per person, not per event
agenda_only = load_agenda_speakers()  # in the agenda but not on the speakers pages (anyone already in the speakers list is not repeated)
speakers = speakers_list + agenda_only  # every unique person once
agenda = load_agenda()
sponsors = load_sponsors()
tickets = load_tickets()

landscape = {r["company"]: r for r in load_ai_landscape()}  # one row per company is enough: the Swiss fields are company-level
swiss_orgs = sum(r["swiss_region"] in ("Zug", "Switzerland") for r in landscape.values())
swiss_pharma = sum(r["swiss_region"] in ("Zug", "Switzerland") and r["company_type"] == "Pharma" for r in landscape.values())
zug_orgs = sum(r["swiss_region"] == "Zug" for r in landscape.values())
all_events = sorted(set(events(speaker_appearances)) | {e for s in agenda_only for e in (s.get("events") or [s["event_name"]])})
st.caption(f"Gold-layer summary across {len(all_events)} NEXT Pharma events")

with st.container(horizontal=True):
    st.metric("Speakers", len(speakers), border=True)
    st.metric("Sessions", len(agenda), border=True)
    st.metric("Sponsors", len(sponsors), border=True)
    st.metric("Events", len(all_events), border=True)
    st.metric("Organization in Switzerland", swiss_orgs, border=True,
              help=f"Companies on the AI landscape map with a headquarters or office in Switzerland: {swiss_pharma} pharma and {swiss_orgs - swiss_pharma} vendors and other organizations. Found by web search, so a company with none listed may still have one.")
    st.metric("Organization in Zug", zug_orgs, border=True,
              help="The same companies, limited to those with an HQ or office in the Zug area (Zug, Baar, Cham, Rotkreuz, Steinhausen and neighbours), where Phamax is based.")

st.subheader("Speaker data completeness")

tier_counts = {"Rich": 0, "Good": 0, "Moderate": 0, "No LinkedIn data": 0}
for s in speakers:
    tier_counts[s["tier"]] += 1

with st.container(border=True):
    # Only show tiers that actually have someone in them -- e.g. "No LinkedIn
    # data" naturally disappears once every gap is covered by an alt-source,
    # without needing to hardcode that removal.
    populated_tiers = [(tier, count) for tier, count in tier_counts.items() if count > 0]
    tier_colors = {"Rich": "green", "Good": "blue", "Moderate": "orange", "No LinkedIn data": "gray"}
    cols = st.columns(len(populated_tiers))
    for col, (tier, count) in zip(cols, populated_tiers):
        with col:
            st.badge(tier, color=tier_colors[tier])
            st.markdown(f"### {count}")

st.subheader("Dataset counts by event")
event_rows = []
for event in all_events:
    event_rows.append(
        {
            "Event": event,
            "Speakers": sum(1 for s in speaker_appearances if s["event_name"] == event),
            "Agenda-only speakers": sum(1 for s in agenda_only if event in (s.get("events") or [s["event_name"]])),
            "Sessions": sum(1 for a in agenda if a["event_name"] == event),
            "Sponsors": sum(1 for sp in sponsors if sp["event_name"] == event),
        }
    )
st.dataframe(event_rows, hide_index=True, width="stretch")
