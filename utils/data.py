"""Data loading for the NEXT Pharma event data explorer.

Reads the gold-layer JSON files produced by the bronze/silver/gold pipelines
under speaker/, speaker_list/, agenda/, sponsors/, and tickets/. Nothing here
writes data -- this is a read-only view over the pipeline's output.
"""
import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.location import clean_location, is_swiss, is_zug_canton, read_pdl_country, validated_presence

ROOT = Path(__file__).resolve().parent.parent

SPEAKERS_GOLD = ROOT / "speaker" / "data" / "gold" / "speakers.json"
SPEAKER_LIST_DIR = ROOT / "speaker_list"
AGENDA_GOLD = ROOT / "agenda" / "data" / "gold" / "sessions.json"
SPONSORS_GOLD = ROOT / "sponsors" / "data" / "gold" / "sponsors.json"
EXHIBITION_STATS_GOLD = ROOT / "sponsors" / "data" / "gold" / "exhibition_stats.json"
TICKETS_GOLD = ROOT / "tickets" / "data" / "gold" / "tickets.json"
AGENDA_SPEAKERS_GOLD = ROOT / "agenda_speaker_list" / "agenda_speakers.json"
AI_LANDSCAPE_GOLD =ROOT / "ai_landscape" / "data" / "gold" / "ai_landscape.parquet"

# Professional-backbone / social-layer fields that decide a speaker's data tier.
# Mirrors the split used in the enrichment coverage report: a profile only
# counts as "rich" when both the career facts and the bio/activity layer are
# present, since LinkedIn gates the second half far more aggressively.
_PROFESSIONAL_FIELDS = ("linkedin_experience", "linkedin_skills", "linkedin_education", "linkedin_current_company")
_SOCIAL_FIELDS = ("linkedin_about", "linkedin_activity")

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')


def _slugify_name(name: str) -> str:
    """Matches speaker_list/scripts/common.py's slugify_name -- must stay in
    sync with the pipeline's folder-naming rule or lookups silently miss."""
    cleaned = _INVALID_CHARS.sub("", name).strip().rstrip(". ")
    return cleaned or "unknown-speaker"


def _load_json(path: Path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(ttl="10m")
def load_enrichment_by_name(base: str = "speaker_list") -> dict:
    """One enrichment record per unique speaker name (not per event
    appearance) -- speakers at two events share a single speaker_list/
    folder, so this is looked up by name rather than record_id.
    base="agenda_speaker_list" reads the agenda speakers' folders instead."""
    enrichment = {}
    base_dir = ROOT / base
    if not base_dir.exists():
        return enrichment
    for folder in base_dir.iterdir():
        if not folder.is_dir() or folder.name == "scripts":
            continue
        gold_path = folder / "data" / "gold" / "linkedin.json"
        data = _load_json(gold_path)
        if data:
            data["pdl_country"] = read_pdl_country(folder)
            enrichment[data["speaker_name"]] = data
    return enrichment


@st.cache_data(ttl="10m")
def load_alt_sources_by_name(base: str = "speaker_list") -> dict:
    """Verified non-LinkedIn sources (company bios, press, conference
    profiles) for speakers LinkedIn couldn't fully cover. See
    speaker_list/scripts/bronze/Bronze-layer-AltSources.py for how each
    entry's identity was confirmed before being added."""
    sources = {}
    base_dir = ROOT / base
    if not base_dir.exists():
        return sources
    for folder in base_dir.iterdir():
        if not folder.is_dir() or folder.name == "scripts":
            continue
        gold_path = folder / "data" / "gold" / "alt_sources.json"
        data = _load_json(gold_path)
        if data:
            sources[data["speaker_name"]] = data
    return sources


def _norm(text) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


@st.cache_data(ttl="10m")
def _swiss_company_index() -> tuple[dict, dict]:
    """(alias -> company, company -> Swiss HQ/office record) from ai_landscape/data/silver/company_gold_map.json and swiss_presence.json."""
    silver = ROOT / "ai_landscape" / "data" / "silver"
    company_map = _load_json(silver / "company_gold_map.json") or {}
    presence = validated_presence((_load_json(silver / "swiss_presence.json") or {}).get("companies", {}))
    alias = {}
    for company, m in company_map.items():
        for a in [company, *m.get("aliases", [])]:
            alias[_norm(a)] = company
    # 'merck' alone is claimed by both Merck KGaA and MSD (Merck & Co.), so it decides nothing; the explicit forms do
    alias.pop("merck", None)
    alias.update({"merckgroup": "Merck KGaA", "merckhealthcare": "Merck KGaA", "merckkgaa": "Merck KGaA", "merckserono": "Merck KGaA"})
    return alias, presence


def _company_of(record: dict, alias: dict):
    """The mapped company a person works for now. The LinkedIn current company decides (exact alias, else the longest alias contained in it, e.g.
    'takeda pharmaceuticals international gmbh glattpark ch' -> Takeda). Only when LinkedIn gives no current company is the event company used,
    so someone who has left (e.g. now an independent consultant) is not tied to their old employer."""
    current = _norm(record.get("linkedin_current_company"))
    if current:
        if current in alias:
            return alias[current]
        inside = [k for k in alias if (len(k) >= 4 and k in current) or (len(k) >= 3 and current.startswith(k))]  # 'msd belgium' -> MSD
        return alias[max(inside, key=len)] if inside else None
    return alias.get(_norm(record.get("company")))


def _add_location(record: dict) -> None:
    """Cleaned location plus Swiss / Zug-canton flags (LinkedIn text first, PDL country as fallback), and whether the person's employer has a
    Swiss HQ or office. The employer is the current company from LinkedIn, else the company at the event, so people who moved are judged on where they are now."""
    loc = clean_location(record.get("linkedin_location"))
    record["linkedin_location"] = loc
    record["swiss_based"] = is_swiss(loc, record.get("pdl_country", ""))
    record["zug_canton"] = is_zug_canton(loc)
    alias, presence = _swiss_company_index()
    company = _company_of(record, alias)
    office = presence.get(company) if company else None
    record["swiss_company"] = company if office else ""
    record["swiss_company_places"] = office["places"] if office else []
    record["swiss_company_zug"] = bool(office and office["zug"])
    record["swiss_via_company_only"] = bool(office) and not record["swiss_based"]  # works for a company with a Swiss office but is located elsewhere


def compute_tier(record: dict) -> str:
    """A verified alt-source bio (see load_alt_sources_by_name) stands in for
    the LinkedIn social/narrative layer (About + Activity) when judging
    completeness -- a speaker with a full professional backbone plus a
    confirmed independent bio is as usable as one with full LinkedIn data,
    even if LinkedIn itself never gave up the About/Activity fields."""
    has_li = bool(record.get("has_enrichment"))
    has_alt = bool(record.get("has_alt_sources")) and not record.get("alt_mention_only")
    prof = sum(bool(record.get(f)) for f in _PROFESSIONAL_FIELDS) if has_li else 0
    soc = sum(bool(record.get(f)) for f in _SOCIAL_FIELDS)

    full_prof = has_li and prof == len(_PROFESSIONAL_FIELDS)
    full_soc = soc == len(_SOCIAL_FIELDS)

    if full_prof and (full_soc or has_alt):
        return "Rich"
    if full_prof or has_alt:
        return "Good"
    if has_li or record.get("has_alt_sources"):
        return "Moderate"  # a mention-only alt source (kind="mention") confirms a session role but gives no bio
    return "No LinkedIn data"


@st.cache_data(ttl="10m")
def load_speakers() -> list[dict]:
    """Every speaker-event appearance from the master roster, each merged
    with that person's LinkedIn enrichment when available. One row per
    appearance (so a two-event speaker appears twice, matching the agenda),
    with the shared enrichment attached to both."""
    master = _load_json(SPEAKERS_GOLD) or []
    enrichment_by_name = load_enrichment_by_name()
    alt_sources_by_name = load_alt_sources_by_name()

    merged = []
    for speaker in master:
        record = dict(speaker)
        enrichment = enrichment_by_name.get(speaker["speaker_name"])
        record["has_enrichment"] = enrichment is not None
        if enrichment:
            for key, value in enrichment.items():
                if key.startswith("linkedin_") or key.endswith("_en"):
                    record[key] = value
            record["enrichment_sources"] = enrichment.get("data_sources", {})
            record["pdl_country"] = enrichment.get("pdl_country", "")
        else:
            record["enrichment_sources"] = {}

        alt = alt_sources_by_name.get(speaker["speaker_name"])
        record["has_alt_sources"] = alt is not None
        record["alt_sources"] = alt.get("sources") if alt else []
        record["alt_sources_verification"] = alt.get("identity_verification") if alt else None

        _add_location(record)
        record["tier"] = compute_tier(record)
        merged.append(record)
    return merged


@st.cache_data(ttl="10m")
def load_agenda_speakers() -> list[dict]:
    """People who speak in the agenda sessions but are NOT in the speakers
    list (built by agenda_speaker_list/scripts/build_agenda_speakers.py;
    anyone already in the speakers list is mapped there, not repeated here).
    Each is merged with the same LinkedIn / alternate-source data the
    speakers list has, so the Speakers page can show them the same way."""
    base = "agenda_speaker_list"
    master = _load_json(AGENDA_SPEAKERS_GOLD) or []
    enrichment_by_name = load_enrichment_by_name(base)
    alt_sources_by_name = load_alt_sources_by_name(base)

    corrections = (_load_json(ROOT / "agenda_speaker_list" / "corrections.json") or {}).get("corrections", {})

    merged = []
    for person in master:
        record = dict(person)
        enrichment = enrichment_by_name.get(person["speaker_name"])
        record["has_enrichment"] = enrichment is not None
        if enrichment:
            for key, value in enrichment.items():
                if key.startswith("linkedin_") or key.endswith("_en"):
                    record[key] = value
            record["enrichment_sources"] = enrichment.get("data_sources", {})
            record["pdl_country"] = enrichment.get("pdl_country", "")
        else:
            record["enrichment_sources"] = {}

        alt = alt_sources_by_name.get(person["speaker_name"])
        record["has_alt_sources"] = alt is not None
        record["alt_sources"] = alt.get("sources") if alt else []
        record["alt_sources_verification"] = alt.get("identity_verification") if alt else None
        record["alt_mention_only"] = bool(alt and alt.get("kind") == "mention")
        record["linkedin_url"] = person.get("linkedin_url") or record.get("linkedin_url")
        fix = corrections.get(person["speaker_name"])
        if fix:
            record.update(fix["fields"])
            record["correction_note"] = fix["why"]
        _add_location(record)
        record["tier"] = compute_tier(record)
        merged.append(record)
    return merged


@st.cache_data(ttl="10m")
def load_agenda() -> list[dict]:
    return _load_json(AGENDA_GOLD) or []


@st.cache_data(ttl="10m")
def load_sponsors() -> list[dict]:
    return _load_json(SPONSORS_GOLD) or []


@st.cache_data(ttl="10m")
def load_exhibition_stats() -> list[dict]:
    return _load_json(EXHIBITION_STATS_GOLD) or []


@st.cache_data(ttl="10m")
def load_tickets() -> list[dict]:
    return _load_json(TICKETS_GOLD) or []


@st.cache_data(ttl="10m")
def load_ai_landscape() -> list[dict]:
    """One row per AI work item (company, concept, source, gold record ids, map position)
    for the AI landscape page. Built by ai_landscape/scripts/gold/layout_work_items.py."""
    if not AI_LANDSCAPE_GOLD.exists():
        return []
    return pd.read_parquet(AI_LANDSCAPE_GOLD).to_dict("records")


def unique_speakers(records: list[dict]) -> list[dict]:
    """Collapse appearance-level records (one per speaker-event) down to one
    row per unique person, by name. Two-event speakers share identical
    enrichment/tier data on both rows, so the first occurrence is enough --
    nothing is lost by dropping the duplicate."""
    seen = set()
    unique = []
    for r in records:
        if r["speaker_name"] in seen:
            continue
        seen.add(r["speaker_name"])
        unique.append(r)
    return unique


def events(records: list[dict]) -> list[str]:
    seen = []
    for r in records:
        if r.get("event_name") and r["event_name"] not in seen:
            seen.append(r["event_name"])
    return sorted(seen)


def initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()
