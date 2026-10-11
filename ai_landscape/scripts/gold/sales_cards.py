"""Sales fields for the map cards: turns the gold-layer JSON into readable, clickable card text and adds account signals.

Used by layout_work_items.py. Reads the real gold files plus the LinkedIn enrichment and alt-source files under speaker_list/, and two
small mapping files:
  ai_landscape/data/silver/company_gold_map.json    which gold records belong to each company
  ai_landscape/data/silver/phamax_customers.json    customers Phamax names publicly (phamax.ch, ariya.ai)

Long fields are written as Markdown, so links (LinkedIn, websites, sources) are clickable on the card; export_atlas.py turns on the
Markdown renderer for those columns.

Company fields (the same on every row of a company):
  phamax_relationship   customer of Phamax / Ariya (with the public source), or not publicly listed
  account_priority      A / B / C for pharma prospects, "Existing customer: expand", or "Vendor / other: competitor or partner"
  priority_why          the points behind the priority
  warm_paths            contacts who previously worked at a Phamax customer (a way in)
  event_footprint       per event: speakers, sessions, sponsor tier, ticket listing
  all_sessions          every session the company's people speak in
  ticket_signal         attendance claims of the events where the company is listed as attending
  sponsor_profile       the company's own sponsor text, tier and website
  key_contacts          every named person (up to 15): title, events, LinkedIn, location, reach, career history, relevant skills
  similar_to_customers  Phamax customers working on the same AI concepts
Item fields:
  gold_evidence         the cited gold record(s) written out
  gold_ref              the record ids, for traceability
"""
import glob
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SILVER = ROOT / "ai_landscape" / "data" / "silver"

SENIOR = re.compile(r"\b(chief|ceo|cto|cdo|cmo|coo|cfo|president|svp|evp|vp|vice president|head|director|general manager|founder|owner|partner|principal)\b", re.I)
LEAD = re.compile(r"\b(lead|manager|senior|executive)\b", re.I)
RELEVANT_SKILL = re.compile(r"\b(ai|artificial|machine learning|genai|generative|llm|analytics|data|digital|automation|omnichannel|crm|insight|commercial excellence|customer experience|medical affairs|market access|launch|marketing)\b", re.I)
TIER_POINTS = {"High": 3, "Medium": 2, "Low": 1, "None": 0}
MAX_CONTACTS = 15


def norm(t):
    return re.sub(r"[^a-z0-9]+", "", (t or "").lower())


def nk(name):
    """Name key that ignores titles, accents-free punctuation and apostrophe variants (Dr Kishan Rees = Kishan Rees, O'Keeffe = O’Keeffe)."""
    t = re.sub(r"\b(dr|prof|mr|mrs|ms)\b\.?", " ", (name or "").lower())
    return re.sub(r"[^a-z0-9]+", "", t)


class NameDict(dict):
    def __init__(self, data=None):
        super().__init__()
        for k, v in (data or {}).items():
            super().__setitem__(nk(k), v)

    def get(self, key, default=None):
        return super().get(nk(key), default)

    def __getitem__(self, key):
        return super().__getitem__(nk(key))

    def __contains__(self, key):
        return super().__contains__(nk(key))

    def setdefault(self, key, default=None):
        return super().setdefault(nk(key), default)


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _clip(t, n):
    t = re.sub(r"\s+", " ", (t or "")).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def md(t):
    """Escape text for Markdown so names and titles cannot break the layout."""
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    for ch in "\\*_[]<>`|":
        t = t.replace(ch, "\\" + ch)
    return t


def link(label, url):
    return f"[{md(label)}]({url})" if url else md(label)


def host(url):
    return re.sub(r"^https?://(www\.)?", "", url or "").rstrip("/")


def _rank(title):
    return 0 if SENIOR.search(title or "") else (1 if LEAD.search(title or "") else 2)


def _cap(t):
    small = {"of", "the", "and", "for", "de", "la", "du", "von", "van", "der", "&"}
    return " ".join(w if w in small else (w.upper() if len(w) <= 3 and w.isalpha() else (w.capitalize() if w.islower() else w)) for w in (t or "").split())


def build(df, items):
    """df: gold dataframe (one row per work item); items: the silver work items (same order). Returns df with the card fields."""
    speakers = {r["record_id"]: r for r in _load(ROOT / "speaker/data/gold/speakers.json")}
    sessions = {r["record_id"]: r for r in _load(ROOT / "agenda/data/gold/sessions.json")}
    sponsors = {r["record_id"]: r for r in _load(ROOT / "sponsors/data/gold/sponsors.json")}
    tickets = {r["record_id"]: r for r in _load(ROOT / "tickets/data/gold/tickets.json")}
    cmap = _load(SILVER / "company_gold_map.json")
    cust = _load(SILVER / "phamax_customers.json")
    by_name = NameDict()
    for r in speakers.values():
        by_name.setdefault(r["speaker_name"], []).append(r)

    # LinkedIn enrichment and alt sources, keyed by speaker name
    li = NameDict()
    # speaker_list = people on the speakers pages; agenda_speaker_list = people who are only in the agenda
    for f in glob.glob(str(ROOT / "speaker_list" / "*" / "data" / "gold" / "linkedin.json")) + glob.glob(str(ROOT / "agenda_speaker_list" / "*" / "data" / "gold" / "linkedin.json")):
        d = _load(f)
        li.setdefault(d["speaker_name"], d)
    corr_path = ROOT / "agenda_speaker_list" / "corrections.json"
    for nm_c, c_ in (_load(corr_path)["corrections"].items() if corr_path.exists() else []):
        if nm_c in li:
            li.get(nm_c).update(c_["fields"])
    alt = NameDict()
    for f in glob.glob(str(ROOT / "speaker_list" / "*" / "data" / "gold" / "alt_sources.json")) + glob.glob(str(ROOT / "agenda_speaker_list" / "*" / "data" / "gold" / "alt_sources.json")):
        d = _load(f)
        alt.setdefault(d["speaker_name"], d)

    # hand-added links for people who are only in the agenda data (no speaker record, so no scraped LinkedIn)
    ov_path = SILVER / "contact_overrides.json"
    overrides_raw = _load(ov_path)["contacts"] if ov_path.exists() else {}
    overrides = NameDict(overrides_raw)
    # which events each agenda person spoke at (for people who have since moved to another company)
    spoke_at = defaultdict(set)
    for s_ in sessions.values():
        for sp_ in s_["speakers"]:
            spoke_at[nk(sp_["speaker_name"])].add(s_["event_name"])

    # ---- Phamax customers
    rel = {c["dataset_company"]: c for c in cust["customers"] if c["dataset_company"]}
    customers = set(rel)
    src_url = cust["sources"]
    cust_pat = re.compile(r"\b(" + "|".join(re.escape(x) for x in ("teva", "tillotts", "angelini", "bavarian nordic", "csl", "vifor", "recordati", "galderma", "takeda", "kalvista", "phathom", "arcera", "pfizer")) + r")\b", re.I)

    def person_card(name, title, events, rec_url, own_aliases, own_is_customer):
        e = li.get(name, {})
        a = alt.get(name)
        url = rec_url or e.get("linkedin_url") or overrides.get(name, {}).get("linkedin_url") or ""
        bits = [f"**{md(name)}**", md(_clip(title, 90)), ", ".join(sorted(events))]
        if url:
            bits.append(link("LinkedIn", url))
        elif a and any(s.get("url") for s in a.get("sources", [])):
            bits.append(link("profile source", next(s["url"] for s in a["sources"] if s.get("url"))))
        if e.get("linkedin_location"):
            bits.append(md(e["linkedin_location"]))
        reach = []
        if e.get("linkedin_followers"):
            reach.append(f"{int(float(e['linkedin_followers'])):,} followers")
        if e.get("linkedin_connections"):
            reach.append(f"{e['linkedin_connections']} connections")
        if reach:
            bits.append(", ".join(reach))
        line1 = " · ".join(b for b in bits if b)
        # second line: where they are now, where they came from, what they say they are good at
        exp = e.get("linkedin_experience") or []
        now = e.get("linkedin_current_company") or ""
        prior, seen = [], set()
        for x in exp:
            c = (x.get("company") or "").strip()
            if c and norm(c) != norm(now) and norm(c) not in seen:
                seen.add(norm(c))
                prior.append(_cap(c))
        skills = [s for s in (e.get("linkedin_skills") or []) if RELEVANT_SKILL.search(s)][:5]
        line2 = []
        if now:
            line2.append(f"Now: {md(_cap(now))}")
        if prior:
            line2.append("Before: " + md(", ".join(prior[:4])))
        if e.get("linkedin_industry"):
            line2.append(f"Industry: {md(e['linkedin_industry'])}")
        if skills:
            line2.append("Skills: " + md(", ".join(skills)))
        tie = None
        if not own_is_customer:
            hits = sorted({m.group(1).title() for c in prior for m in [cust_pat.search(c)] if m and norm(m.group(1)) not in own_aliases})
            if hits:
                tie = hits
                line2.append("**Warm tie: previously at " + md(", ".join(hits)) + " (Phamax customer)**")
        upd = overrides.get(name, {}).get("update")
        if upd:
            line2.append("**Update:** " + md(upd))
        card = "- " + line1 + ("<br>" + " · ".join(line2) if line2 else "")
        return card, tie

    # ---- company-level facts from the gold files
    facts = {}
    for co, m in cmap.items():
        al = set(m["aliases"])
        own_is_customer = co in customers
        events = defaultdict(lambda: {"speakers": set(), "sessions": set(), "sponsor": [], "ticket": False})
        people = {}  # name -> {"title", "events", "url"}
        canon_map = {}

        def canon(nm):
            # one person, one entry, even when the speaker list and the agenda spell the name differently
            return canon_map.setdefault(nk(nm), nm)

        for rid in m["speakers"]:
            r = speakers[rid]
            nm0 = canon(r["speaker_name"])
            p = people.setdefault(nm0, {"title": r["designation"], "events": set(), "url": r.get("linkedin_url") or ""})
            p["events"].add(r["event_name"])
            events[r["event_name"]]["speakers"].add(nm0)
        for rid in m["sessions"]:
            s = sessions[rid]
            events[s["event_name"]]["sessions"].add(rid)
            for sp in s["speakers"]:
                nm = canon(sp["speaker_name"])
                belongs = norm(sp.get("company")) in al or nm in people
                if not belongs and not sp.get("company"):
                    belongs = any(norm(x.get("company")) in al for x in by_name.get(nm, []))
                if belongs:
                    events[s["event_name"]]["speakers"].add(nm)
                    p = people.setdefault(nm, {"title": sp["designation"], "events": set(), "url": (by_name.get(nm) or [{}])[0].get("linkedin_url") or ""})
                    p["events"].add(s["event_name"])
        for rid in m["sponsors"]:
            sp = sponsors[rid]
            events[sp["event_name"]]["sponsor"].append(sp)
        for rid in m["tickets"]:
            events[tickets[rid]["event_name"]]["ticket"] = True
        # people who spoke for another company but have since joined this one (checked on their LinkedIn page)
        for nm_o, ov in overrides_raw.items():
            if ov.get("moved_to") == co and nm_o not in people:
                people[nm_o] = {"title": ov.get("new_title", ""), "events": set(spoke_at.get(nk(nm_o), set())), "url": ov["linkedin_url"], "moved": True}

        foot = []
        for ev in sorted(events):
            e = events[ev]
            bits = []
            if e["speakers"]:
                bits.append(f"{len(e['speakers'])} speaker{'s' if len(e['speakers']) != 1 else ''}")
            if e["sessions"]:
                bits.append(f"{len(e['sessions'])} session{'s' if len(e['sessions']) != 1 else ''}")
            if e["sponsor"]:
                bits.append(f"{(e['sponsor'][0].get('sponsorship_tier') or 'sponsor').title()} sponsor")
            if e["ticket"]:
                bits.append("listed among attending companies")
            foot.append(f"{ev}: " + ", ".join(bits))

        sess_lines = []
        for rid in sorted(m["sessions"], key=lambda r: (sessions[r]["event_name"], sessions[r]["day"], sessions[r]["start_time"])):
            s = sessions[rid]
            sess_lines.append(f"- {md(s['session_title'])} · {s['event_name']}, {s['day']} {s['start_time']}")

        tick = []
        for rid in m["tickets"]:
            t = tickets[rid]
            tick.append(f"Listed among attending companies at {t['event_name']} ({'; '.join(t.get('stats') or [])})")

        spons = []
        for e in events.values():
            for sp in e["sponsor"]:
                web = sp.get("website_url") or ""
                spons.append(f"- **{md((sp.get('sponsorship_tier') or 'Sponsor').title())} sponsor, {sp['event_name']}** · {link(host(web), web) if web else ''}" + (f"<br>{md(_clip(sp.get('description'), 300))}" if sp.get("description") else ""))

        ordered = sorted(people.items(), key=lambda kv: (_rank(kv[1]["title"]), kv[0]))
        cards, ties = [], []
        for nm, p in ordered[:MAX_CONTACTS]:
            card, tie = person_card(nm, p["title"], p["events"], p["url"], al, own_is_customer)
            cards.append(card)
            if tie:
                ties.append(f"- **{md(nm)}** ({md(_clip(p['title'], 60))}): previously at {md(', '.join(tie))}")
        if len(ordered) > MAX_CONTACTS:
            cards.append(f"- … and {len(ordered) - MAX_CONTACTS} more named people in the gold data")
        facts[co] = {
            "footprint": " | ".join(foot) if foot else "Not found in the speaker, agenda, sponsor or ticket data",
            "sessions": "\n".join(sess_lines) if sess_lines else "No sessions in the agenda data",
            "tickets": " | ".join(tick) if tick else "Not listed among attending companies",
            "sponsor_profile": "\n".join(spons) if spons else "Not a sponsor",
            "contacts": "\n".join(cards) if cards else "No named contacts in the gold data",
            "warm": "\n".join(ties) if ties else "None found", "n_events": len(events), "sponsor": bool(spons),
            "senior": sum(1 for v in people.values() if _rank(v["title"]) == 0),
        }

    # ---- AI concept profile per company (real work items only) for the lookalike hint
    concepts = defaultdict(set)
    scope = defaultdict(bool)
    for _, r in df.iterrows():
        if r["concept"] != "No AI evidence found":
            concepts[r["company"]].add(r["concept"])
            if r["decision_intelligence_fit"] == "Yes":
                scope[r["company"]] = True
    cust_concepts = {c: concepts[c] for c in customers if concepts.get(c)}

    company_fields = {}
    for co in df["company"].unique():
        tier = df.loc[df.company == co, "relevance"].iloc[0]
        f = facts[co]
        why = [f"AI relevance {tier}"]
        score = TIER_POINTS[tier]
        if scope[co]:
            score += 1
            why.append("AI work fits Insights, Commercial or Medical teams")
        if f["n_events"] >= 2:
            score += 1
            why.append(f"seen at {f['n_events']} events")
        if f["sponsor"]:
            score += 1
            why.append("event sponsor (has marketing budget)")
        if f["senior"]:
            score += 1
            why.append(f"{f['senior']} senior named contact{'s' if f['senior'] != 1 else ''}")
        if co in customers:
            c = rel[co]
            priority = "Existing customer: expand"
            relationship = "Phamax customer, listed on " + " and ".join(link(s, src_url[s]) for s in c["listed_on"]) + (f" (as {md(c['name'])})" if c["name"] != co else "")
            similar = "-"
        else:
            is_pharma = df.loc[df.company == co, "company_type"].iloc[0] == "Pharma"
            if is_pharma:
                priority = "A: approach now" if score >= 6 else ("B: nurture" if score >= 4 else "C: monitor")
            else:
                priority = "Vendor / other: competitor or partner"
            relationship = "Not publicly listed as a Phamax customer (phamax.ch and ariya.ai name only some customers)"
            shared = sorted(((len(concepts[co] & cc), cn) for cn, cc in cust_concepts.items() if concepts[co] & cc), key=lambda x: (-x[0], x[1]))
            similar = ", ".join(f"{cn} ({k} shared concept{'s' if k != 1 else ''})" for k, cn in shared[:3]) or "No overlap with listed customers"
        company_fields[co] = {
            "phamax_relationship": relationship, "account_priority": priority, "priority_why": f"Score {score} of 7: " + "; ".join(why),
            "warm_paths": f["warm"], "event_footprint": f["footprint"], "all_sessions": f["sessions"], "ticket_signal": f["tickets"],
            "sponsor_profile": f["sponsor_profile"], "key_contacts": f["contacts"], "similar_to_customers": similar,
        }

    # ---- item-level: the cited gold record(s) written out
    def describe(g):
        f, rid = g["file"], g["record_id"]
        if f == "speakers.json":
            r = speakers[rid]
            return f"**Speaker ({r['event_name']}):** {md(r['speaker_name'])}, {md(r['designation'])}" + (f" · {link('LinkedIn', r['linkedin_url'])}" if r.get("linkedin_url") else "")
        if f == "sessions.json":
            s = sessions[rid]
            def person_url(nm):
                return (by_name.get(nm) or [{}])[0].get("linkedin_url") or li.get(nm, {}).get("linkedin_url") or overrides.get(nm, {}).get("linkedin_url") or ""

            panel = "".join(
                f"<br>• {link(p['speaker_name'], person_url(p['speaker_name']))}, {md(_clip(p['designation'], 70))}" + (f" ({md(p['company'])})" if p.get("company") else "")
                for p in s["speakers"]
            )
            return f"**Session ({s['event_name']}, {s['day']} {s['start_time']}, {md(s['track'])}):** {md(s['session_title'])}" + (f"<br>**Panel:**{panel}" if panel else "")
        if f == "sponsors.json":
            s = sponsors[rid]
            web = s.get("website_url") or ""
            return f"**Sponsor ({md((s.get('sponsorship_tier') or '').title())}, {s['event_name']}):** {md(s['organization_name'])} · {link(web, web) if web else ''}<br>{md(_clip(s.get('description'), 400))}"
        if f == "tickets.json":
            return f"**Listed among attending companies ({tickets[rid]['event_name']})**"
        return rid

    evidence, ref = [], []
    for it in items:
        recs = it["gold_records"]
        if it["concept_code"] == "J":
            kinds = Counter(g["file"].split(".")[0] for g in recs)
            evidence.append("Appears in the gold data (" + ", ".join(f"{v} {k}" for k, v in kinds.items()) + "), but no AI content found. See the contacts and sessions above.")
        elif recs:
            evidence.append("<br><br>".join(describe(g) for g in recs))
        else:
            evidence.append("None: web source only (see source_url)")
        ref.append(" | ".join(f"{g['file']}:{g['record_id']}" for g in recs) if recs else "-")

    out = df.drop(columns=[c for c in ("gold_records", "all_sources") if c in df.columns]).copy()
    for col in ("phamax_relationship", "account_priority", "priority_why", "warm_paths", "event_footprint", "all_sessions", "ticket_signal", "sponsor_profile", "key_contacts", "similar_to_customers"):
        out[col] = out["company"].map(lambda c: company_fields[c][col])
    out["gold_evidence"] = evidence
    out["gold_ref"] = ref
    return out
