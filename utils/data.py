"""Data loading for the NEXT Pharma event data explorer.

Reads the gold-layer JSON files produced by the bronze/silver/gold pipelines
under speaker/, speaker_list/, agenda/, sponsors/, and tickets/. Nothing here
writes data -- this is a read-only view over the pipeline's output.
"""
import json
import re
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent

SPEAKERS_GOLD = ROOT / "speaker" / "data" / "gold" / "speakers.json"
SPEAKER_LIST_DIR = ROOT / "speaker_list"
AGENDA_GOLD = ROOT / "agenda" / "data" / "gold" / "sessions.json"
SPONSORS_GOLD = ROOT / "sponsors" / "data" / "gold" / "sponsors.json"
EXHIBITION_STATS_GOLD = ROOT / "sponsors" / "data" / "gold" / "exhibition_stats.json"
TICKETS_GOLD = ROOT / "tickets" / "data" / "gold" / "tickets.json"

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
def load_enrichment_by_name() -> dict:
    """One enrichment record per unique speaker name (not per event
    appearance) -- speakers at two events share a single speaker_list/
    folder, so this is looked up by name rather than record_id."""
    enrichment = {}
    if not SPEAKER_LIST_DIR.exists():
        return enrichment
    for folder in SPEAKER_LIST_DIR.iterdir():
        if not folder.is_dir() or folder.name == "scripts":
            continue
        gold_path = folder / "data" / "gold" / "linkedin.json"
        data = _load_json(gold_path)
        if data:
            enrichment[data["speaker_name"]] = data
    return enrichment


@st.cache_data(ttl="10m")
def load_alt_sources_by_name() -> dict:
    """Verified non-LinkedIn sources (company bios, press, conference
    profiles) for speakers LinkedIn couldn't fully cover. See
    speaker_list/scripts/bronze/Bronze-layer-AltSources.py for how each
    entry's identity was confirmed before being added."""
    sources = {}
    if not SPEAKER_LIST_DIR.exists():
        return sources
    for folder in SPEAKER_LIST_DIR.iterdir():
        if not folder.is_dir() or folder.name == "scripts":
            continue
        gold_path = folder / "data" / "gold" / "alt_sources.json"
        data = _load_json(gold_path)
        if data:
            sources[data["speaker_name"]] = data
    return sources


def compute_tier(record: dict) -> str:
    """A verified alt-source bio (see load_alt_sources_by_name) stands in for
    the LinkedIn social/narrative layer (About + Activity) when judging
    completeness -- a speaker with a full professional backbone plus a
    confirmed independent bio is as usable as one with full LinkedIn data,
    even if LinkedIn itself never gave up the About/Activity fields."""
    has_li = bool(record.get("has_enrichment"))
    has_alt = bool(record.get("has_alt_sources"))
    prof = sum(bool(record.get(f)) for f in _PROFESSIONAL_FIELDS) if has_li else 0
    soc = sum(bool(record.get(f)) for f in _SOCIAL_FIELDS)

    full_prof = has_li and prof == len(_PROFESSIONAL_FIELDS)
    full_soc = soc == len(_SOCIAL_FIELDS)

    if full_prof and (full_soc or has_alt):
        return "Rich"
    if full_prof or has_alt:
        return "Good"
    if has_li:
        return "Moderate"
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
        else:
            record["enrichment_sources"] = {}

        alt = alt_sources_by_name.get(speaker["speaker_name"])
        record["has_alt_sources"] = alt is not None
        record["alt_sources"] = alt.get("sources") if alt else []
        record["alt_sources_verification"] = alt.get("identity_verification") if alt else None

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
