import streamlit as st

from utils.data import (
    events,
    load_agenda,
    load_speakers,
    load_sponsors,
    load_tickets,
    unique_speakers,
)

st.title("Overview", icon=":material/home:")

speaker_appearances = load_speakers()
speakers = unique_speakers(speaker_appearances)  # one row per person, not per event
agenda = load_agenda()
sponsors = load_sponsors()
tickets = load_tickets()

all_events = events(speaker_appearances)
st.caption(f"Gold-layer summary across {len(all_events)} NEXT Pharma events")

with st.container(horizontal=True):
    st.metric("Speakers", len(speakers), border=True)
    st.metric("Sessions", len(agenda), border=True)
    st.metric("Sponsors", len(sponsors), border=True)
    st.metric("Events", len(all_events), border=True)
st.caption(f"{len(speaker_appearances)} speaker-event appearances across {len(all_events)} events "
           f"({len(speaker_appearances) - len(speakers)} people spoke at more than one)")

st.subheader("Speaker data completeness")
st.caption("From LinkedIn plus verified non-LinkedIn sources where LinkedIn fell short -- "
           "see the Speakers page for detail on any profile.")

linkedin_count = sum(1 for s in speakers if s["has_enrichment"])
alt_source_count = sum(1 for s in speakers if s["has_alt_sources"])
any_data_count = sum(1 for s in speakers if s["has_enrichment"] or s["has_alt_sources"])
tier_counts = {"Rich": 0, "Good": 0, "Moderate": 0, "No LinkedIn data": 0}
for s in speakers:
    tier_counts[s["tier"]] += 1

with st.container(border=True):
    st.markdown(f"**{any_data_count} of {len(speakers)}** unique speakers have some data attached "
                f"({linkedin_count} via LinkedIn, {alt_source_count} via a verified alternate source "
                f"-- these overlap for speakers who have both).")
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
st.caption("Speakers here counts appearances (an event's own headcount), while the totals above count unique people.")
event_rows = []
for event in all_events:
    event_rows.append(
        {
            "Event": event,
            "Speakers": sum(1 for s in speaker_appearances if s["event_name"] == event),
            "Sessions": sum(1 for a in agenda if a["event_name"] == event),
            "Sponsors": sum(1 for sp in sponsors if sp["event_name"] == event),
        }
    )
st.dataframe(event_rows, hide_index=True, width="stretch")
