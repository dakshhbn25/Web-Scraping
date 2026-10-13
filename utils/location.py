"""Where a speaker is based, from the scraped LinkedIn location and PDL's country.

Pure functions (no Streamlit), so the app and the map build (ai_landscape/scripts/gold/sales_cards.py) share one rule.
The LinkedIn page text is the primary source; PDL's country is the fallback when the LinkedIn location is missing or unusable.
"""
import json
import re
from pathlib import Path

_CH_WORDS = re.compile(r"switzerland|schweiz|suisse|svizzera", re.I)
_CH_CODE = re.compile(r"(,|\s)CH$")
_ZUG_CANTON = re.compile(r"\b(zug|baar|cham|rotkreuz|risch|steinhausen|h[uü]nenberg|unter[aä]geri|ober[aä]geri|walchwil|menzingen|neuheim|pf[aä]ffikon zg)\b", re.I)


def clean_location(loc) -> str:
    """The LinkedIn location, or "" when the scrape captured page chrome (cookie banner, sign-in text, markdown) instead of a place."""
    loc = re.sub(r"\s+", " ", str(loc or "")).strip()
    if len(loc) > 80 or re.search(r"linkedin|cookie|\]\(|skip to|sign in|join now", loc, re.I):
        return ""
    parts, seen = [], set()
    for part in (p.strip() for p in loc.split(",")):  # 'Zug, Zug, Switzerland, CH' -> 'Zug, Switzerland, CH'
        if part and part.lower() not in seen:
            seen.add(part.lower())
            parts.append(part)
    return ", ".join(parts)


def read_pdl_country(person_folder) -> str:
    """PDL's country for a person (lowercase), from the bronze file; "" if absent. The free tier hides the city but keeps the country."""
    path = Path(person_folder) / "data" / "bronze" / "linkedin_pdl.json"
    try:
        raw = json.load(open(path, encoding="utf-8")).get("raw") or {}
    except (OSError, ValueError):
        return ""
    country = raw.get("location_country")
    return country.lower() if isinstance(country, str) else ""


def is_swiss(location, pdl_country="") -> bool:
    loc = clean_location(location)
    if loc:
        return bool(_CH_WORDS.search(loc) or _CH_CODE.search(loc))
    return (pdl_country or "").lower() == "switzerland"


def is_zug_canton(location) -> bool:
    return bool(_ZUG_CANTON.search(clean_location(location)))


def validated_presence(companies: dict) -> dict:
    """Only the Swiss HQ/office entries that passed ai_landscape/scripts/silver/validate_swiss_presence.py, and only their confirmed places.

    An entry without a passing validation block is dropped, 'HQ' is kept only when a headquarters statement was found, and `zug` is
    recomputed from the confirmed places. Nothing unchecked reaches a card or a page."""
    out = {}
    for name, entry in companies.items():
        v = entry.get("validation") or {}
        places = v.get("places_confirmed") or []
        if not str(v.get("status", "")).startswith("confirmed") or not places:
            continue
        out[name] = {**entry, "places": places, "kind": "HQ" if entry.get("kind") == "HQ" and v.get("hq_confirmed") else "Office",
                     "zug": any(is_zug_canton(p) for p in places)}
    return out
