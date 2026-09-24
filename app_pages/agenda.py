from datetime import datetime

import streamlit as st

from utils.data import events, load_agenda

TRACK_ORDER = ["MAIN STAGE", "INNOVATION STAGE", "AI STAGE", "Learn Stage"]


def track_sort_key(track):
    return TRACK_ORDER.index(track) if track in TRACK_ORDER else len(TRACK_ORDER)


def time_sort_key(session):
    try:
        return datetime.strptime(session.get("start_time") or "", "%I:%M %p")
    except ValueError:
        return datetime.min


st.title("Agenda", icon=":material/event_note:")

agenda = load_agenda()
all_events = events(agenda)

with st.sidebar:
    st.subheader("Filters")
    selected_event = st.selectbox("Event", all_events, index=0 if all_events else None)

day_options = sorted({a["day"] for a in agenda if a["event_name"] == selected_event and a.get("day")})
selected_day = st.segmented_control("Day", day_options, default=day_options[0] if day_options else None)

sessions = [a for a in agenda if a["event_name"] == selected_event and (not selected_day or a.get("day") == selected_day)]

tracks = sorted({s.get("track") for s in sessions if s.get("track")}, key=track_sort_key)

st.caption(f"{selected_event} · {selected_day or 'all days'} · {len(sessions)} sessions across {len(tracks)} tracks")

if not tracks:
    st.info("No sessions match the current filters.")
else:
    tabs = st.tabs([f"{t} ({sum(1 for s in sessions if s.get('track') == t)})" for t in tracks])
    for tab, track in zip(tabs, tracks):
        with tab:
            track_sessions = sorted((s for s in sessions if s.get("track") == track), key=time_sort_key)
            for s in track_sessions:
                with st.container(border=True):
                    st.caption(f"{s.get('start_time', '')} - {s.get('end_time', '')}")
                    st.markdown(f"**{s.get('session_title')}**")

                    speakers = s.get("speakers") or []
                    if speakers:
                        st.space("small")
                        for sp in speakers:
                            st.markdown(f"**{sp['speaker_name']}**")
                            role_line = " at ".join(
                                part for part in [sp.get("designation"), sp.get("company")] if part
                            )
                            st.caption(role_line or "—")