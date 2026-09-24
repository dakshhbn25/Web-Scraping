import re

import streamlit as st

from utils.data import events, initials, load_speakers

PAGE_SIZE = 12
TIER_COLOR = {"Rich": "green", "Good": "blue", "Moderate": "orange", "No LinkedIn data": "gray"}


@st.dialog("Speaker profile", width="large")
def show_detail(record: dict):
    name = record["speaker_name"]
    col_avatar, col_head = st.columns([1, 6], vertical_alignment="center")
    with col_avatar:
        st.badge(initials(name), color=TIER_COLOR[record["tier"]])
    with col_head:
        st.markdown(f"### {name}")
        st.caption(f"{record['event_name']} · {record.get('event_year', '')}")

    st.badge(record["tier"], color=TIER_COLOR[record["tier"]], icon=":material/verified:")
    sources = record.get("enrichment_sources") or {}
    active = [n for n, on in [("Tavily", sources.get("tavily")), ("PDL", sources.get("pdl"))] if on]
    if record.get("has_alt_sources"):
        active.append(f"{len(record.get('alt_sources') or [])} verified non-LinkedIn source(s)")
    if active:
        st.caption(f"Data from: {' + '.join(active)}")

    st.divider()

    tab_names = ["Overview", "Career", "Activity"]
    if record.get("has_alt_sources"):
        tab_names.append("Other sources")
    tabs = st.tabs(tab_names)
    tab_overview, tab_career, tab_activity = tabs[0], tabs[1], tabs[2]
    tab_alt = tabs[3] if len(tabs) > 3 else None

    with tab_overview:
        st.markdown("**Designation**")
        st.write(record.get("designation") or "—")
        st.markdown("**Company**")
        st.write(record.get("linkedin_current_company") or record.get("company") or "—")

        loc = record.get("linkedin_location")
        if loc:
            st.markdown("**Location**")
            st.write(loc)

        about = record.get("linkedin_about_en") or record.get("linkedin_about")
        if about:
            st.markdown("**About**")
            st.write(about)
            if record.get("linkedin_about") and record.get("linkedin_about_en"):
                with st.expander("Show original language"):
                    st.write(record["linkedin_about"])

        with st.container(horizontal=True):
            if record.get("linkedin_connections"):
                st.metric("Connections", record["linkedin_connections"], border=True)
            if record.get("linkedin_followers"):
                st.metric("Followers", record["linkedin_followers"], border=True)

        languages = record.get("linkedin_languages_en") or record.get("linkedin_languages")
        if languages:
            st.markdown("**Languages**")
            st.write(languages)

        if record.get("linkedin_url"):
            st.link_button("View LinkedIn profile", record["linkedin_url"], icon=":material/open_in_new:")
        if record.get("source_urls"):
            st.link_button("View source page", record["source_urls"][0], icon=":material/link:")

    with tab_career:
        skills = record.get("linkedin_skills") or []
        if skills:
            st.markdown(f"**Skills** ({len(skills)})")
            shown = skills[:24]
            with st.container(horizontal=True, wrap=True):
                for skill in shown:
                    st.badge(skill, color="gray")
            if len(skills) > len(shown):
                with st.expander(f"+{len(skills) - len(shown)} more skills"):
                    st.write(", ".join(skills[len(shown):]))

        experience = record.get("linkedin_experience") or []
        if experience:
            st.markdown(f"**Experience** ({len(experience)} roles)")
            for role in experience:
                title = role.get("title", "")
                if role.get("redacted"):
                    st.caption("Role hidden by LinkedIn (not visible without login)")
                    continue
                company = role.get("company")
                dates = " - ".join(d for d in [role.get("start_date"), role.get("end_date")] if d) or role.get("duration")
                label = f"**{title}**"
                if company and company != title:
                    label += f" · {company}"
                st.markdown(label)
                if dates:
                    st.caption(dates)

        education = record.get("linkedin_education")
        if education:
            st.markdown("**Education**")
            if isinstance(education, list):
                for edu in education:
                    school = edu.get("school")
                    if not school:
                        continue
                    majors = ", ".join(edu.get("majors") or [])
                    # PDL gives start_date/end_date; the Tavily fallback gives one duration string.
                    dates = " - ".join(d for d in [edu.get("start_date"), edu.get("end_date")] if d) or edu.get("duration")
                    st.markdown(f"**{school}**" + (f" · {majors}" if majors else ""))
                    if dates:
                        st.caption(dates)
            else:
                st.text(education)  # legacy string shape from data scraped before the parser existed

        certs = record.get("linkedin_certifications_en") or record.get("linkedin_certifications")
        if certs:
            st.markdown("**Certifications**")
            st.text(certs)

        honors = record.get("linkedin_honors_and_awards_en") or record.get("linkedin_honors_and_awards")
        if honors:
            st.markdown("**Honours & awards**")
            st.text(honors)

        if not (skills or experience or education):
            st.caption("No career data available for this speaker.")

    with tab_activity:
        posts = record.get("linkedin_activity") or []
        if posts:
            st.markdown(f"**Recent activity** ({len(posts)} posts)")
            for post in posts[:8]:
                with st.container(border=True):
                    st.write(post.get("text_en") or post.get("text"))
                    if post.get("text_en") and post.get("text") and post["text_en"] != post["text"]:
                        with st.expander("Original language"):
                            st.write(post["text"])
                    meta = post.get("interaction")
                    if meta:
                        st.caption(meta)
                    if post.get("post_url"):
                        st.link_button("View post", post["post_url"], icon=":material/open_in_new:")
            if len(posts) > 8:
                st.caption(f"+{len(posts) - 8} more posts not shown")
        else:
            st.caption("No activity data available for this speaker.")

        related = record.get("linkedin_people_also_viewed") or []
        if related:
            st.markdown(f"**People also viewed** ({len(related)})")
            st.dataframe(
                [{"Name": r.get("name"), "Company": r.get("company")} for r in related[:10]],
                hide_index=True,
                width="stretch",
            )

    if tab_alt:
        with tab_alt:
            st.caption("LinkedIn access was incomplete for this speaker, so these independently "
                       "verified sources fill the gap.")
            verification = record.get("alt_sources_verification")
            if verification:
                st.info(verification, icon=":material/verified_user:")
            for src in record.get("alt_sources") or []:
                with st.container(border=True):
                    st.markdown(f"**{src.get('title') or src['url']}**")
                    text = (src.get("text") or "").strip()
                    # Some JS-rendered pages get scraped mid-render, leaving a
                    # "Loading...\n\nEdited <date>\n\n" stub before the real
                    # content (e.g. futures4europe.eu) -- drop it for display.
                    text = re.sub(r"^Loading\.\.\.\s*\n+Edited[^\n]*\n+", "", text)
                    preview = text[:600] + ("..." if len(text) > 600 else "")
                    st.write(preview)
                    st.link_button("View source", src["url"], icon=":material/open_in_new:")


st.title("Speakers", icon=":material/groups:")

speakers = load_speakers()
all_events = events(speakers)

TIER_ORDER = ["Rich", "Good", "Moderate", "No LinkedIn data"]
available_tiers = [t for t in TIER_ORDER if any(s["tier"] == t for s in speakers)]

with st.sidebar:
    st.subheader("Filters")
    selected_event = st.selectbox("Event", ["All events"] + all_events)
    tier_filter = st.pills(
        "Data completeness",
        available_tiers,
        selection_mode="multi",
        default=available_tiers,
    )

search = st.text_input(
    "Search speakers",
    placeholder="Search by name, company, or title...",
    icon=":material/search:",
)

filtered = speakers
if selected_event != "All events":
    filtered = [s for s in filtered if s["event_name"] == selected_event]
filtered = [s for s in filtered if s["tier"] in (tier_filter or [])]
if search:
    q = search.lower()
    filtered = [
        s
        for s in filtered
        if q in s["speaker_name"].lower()
        or q in (s.get("designation") or "").lower()
        or q in (s.get("company") or "").lower()
    ]

st.caption(f"Showing {len(filtered)} of {len(speakers)} speaker appearances")

if not filtered:
    st.info("No speakers match the current filters.")
else:
    num_pages = max(1, (len(filtered) + PAGE_SIZE - 1) // PAGE_SIZE)
    with st.container(horizontal_alignment="right"):
        current_page = st.pagination(num_pages, key="speakers_page") if num_pages > 1 else 1

    start = (current_page - 1) * PAGE_SIZE
    page_items = filtered[start : start + PAGE_SIZE]

    for record in page_items:
        with st.container(border=True):
            col_avatar, col_body, col_action = st.columns([1, 5, 2], vertical_alignment="center")
            with col_avatar:
                st.badge(initials(record["speaker_name"]), color=TIER_COLOR[record["tier"]])
            with col_body:
                st.markdown(f"**{record['speaker_name']}**")
                st.caption(f"{record['event_name']} · {record.get('designation') or 'Speaker'}"
                           + (f" at {record['company']}" if record.get("company") else ""))
            with col_action:
                with st.container(horizontal=True, horizontal_alignment="right"):
                    st.badge(record["tier"], color=TIER_COLOR[record["tier"]])
                    if st.button("View details", key=f"view_{record['record_id']}", icon=":material/visibility:"):
                        show_detail(record)
