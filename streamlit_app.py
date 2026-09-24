import streamlit as st

st.set_page_config(page_title="NEXT Pharma - event data explorer", layout="wide")

page = st.navigation(
    [
        st.Page("app_pages/home.py", title="Home", icon=":material/home:"),
        st.Page("app_pages/speakers.py", title="Speakers", icon=":material/groups:"),
        st.Page("app_pages/agenda.py", title="Agenda", icon=":material/event_note:"),
        st.Page("app_pages/sponsors.py", title="Sponsors", icon=":material/handshake:"),
        st.Page("app_pages/tickets.py", title="Tickets", icon=":material/confirmation_number:"),
    ],
    position="sidebar",
)

with st.sidebar:
    st.markdown("**NEXT Pharma**")
    st.caption("Event data explorer")
    st.divider()

page.run()
