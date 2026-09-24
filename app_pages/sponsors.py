import streamlit as st

from utils.data import events, load_sponsors

st.title("Sponsors", icon=":material/handshake:")

sponsors = load_sponsors()
all_events = events(sponsors)

with st.sidebar:
    st.subheader("Filters")
    selected_event = st.selectbox("Event", ["All events"] + all_events)

filtered = sponsors if selected_event == "All events" else [s for s in sponsors if s["event_name"] == selected_event]

tier_order = ["Platinum", "Gold", "Silver", "Media", "Exhibitor", "Knowledge"]
filtered.sort(key=lambda s: (tier_order.index(s["sponsorship_tier"]) if s.get("sponsorship_tier") in tier_order else len(tier_order), s.get("organization_name") or ""))

st.caption(f"Showing {len(filtered)} of {len(sponsors)} sponsors")

tier_color = {"Platinum": "violet", "Gold": "orange", "Silver": "gray", "Media": "blue", "Exhibitor": "green", "Knowledge": "red"}

cols = st.columns(3)
for i, sponsor in enumerate(filtered):
    with cols[i % 3]:
        with st.container(border=True, height="stretch"):
            tier = sponsor.get("sponsorship_tier") or "Sponsor"
            st.badge(f"{tier.upper()} · {sponsor['event_name']}", color=tier_color.get(tier, "gray"))
            st.markdown(f"**{sponsor['organization_name']}**")
            st.caption(sponsor.get("description") or "No description available.")
            if sponsor.get("website_url"):
                st.link_button("Website", sponsor["website_url"], icon=":material/open_in_new:")
