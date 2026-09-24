import streamlit as st

from utils.data import load_tickets

st.title("Tickets", icon=":material/confirmation_number:")
st.caption("Sold-out claims and attendance stats per event")

for ticket in load_tickets():
    with st.container(border=True):
        st.subheader(ticket["event_name"])
        st.write(" · ".join([ticket.get("sold_out_claim", "")] + (ticket.get("stats") or [])))

        companies = ticket.get("attendee_companies") or []
        if companies:
            st.markdown(f"**{len(companies)} attendee companies listed**")
            names = [c["company_name"] for c in companies]
            with st.expander("View companies"):
                st.write(", ".join(names))
        else:
            st.caption("Attendee companies not listed on source page")
