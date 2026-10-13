"""Validation gate for ai_landscape/data/silver/swiss_presence.json.

For every entry this opens the cited source page and checks, in the page text itself, that
  1. the company (its name or a known alias) is mentioned, and
  2. each place listed for it is mentioned.
A place that is not found in the source is NOT confirmed and is not used on the cards. An entry counts only if at least one place is
confirmed (a generic 'Switzerland' entry needs the company plus a Swiss marker). 'HQ' is kept only if the page also says headquarters.
Results are written back into the file (validation block per entry) and a readable report is printed.

Pages that block a plain request (403, JavaScript only, PDF) are read through Firecrawl when FIRECRAWL_API_KEY is set. A page that still
cannot be read is reported as 'could not fetch' and stays unconfirmed until someone checks it by hand and records the evidence in
validation_manual.json next to the data file.

Run:  .venv/Scripts/python.exe ai_landscape/scripts/silver/validate_swiss_presence.py
"""
import html
import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]
SILVER = ROOT / "ai_landscape" / "data" / "silver"
FILE = SILVER / "swiss_presence.json"
MANUAL = SILVER / "validation_manual.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36", "Accept-Language": "en,de;q=0.8"}
HQ_WORDS = re.compile(r"headquarter|head office|hauptsitz|siege|siège|\bHQ\b|sitz", re.I)
SWISS_MARK = re.compile(r"switzerland|schweiz|suisse|svizzera|\bCH-\d{4}\b")


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", html.unescape(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text.lower())


def place_token(place: str) -> str:
    """'Baar (ZG)' -> 'baar'; 'Zurich (Glattpark-Opfikon)' -> 'zurich'; 'Geneva (GE)' -> 'geneva'."""
    return norm(re.sub(r"\(.*?\)", "", place)).strip()


VARIANTS = {"zurich": "zurich|zuerich|zurigo", "geneva": "geneva|geneve|genf", "basel": "basel|bale|basilea", "lucerne": "lucerne|luzern|lucerna",
            "bern": "bern|berne", "neuchatel": "neuchatel|neuenburg", "villars-sur-glane": "villars-sur-glane|villars sur glane",
            "saint-prex": "saint-prex|st-prex|st prex"}


def place_pattern(place: str) -> str:
    """Regex for a place, including its other-language spellings (Genève / Geneva / Genf)."""
    tok = place_token(place)
    return r"\b(?:" + VARIANTS.get(tok, re.escape(tok)) + r")\b"


def firecrawl_text(url: str):
    """Fallback reader for pages that block a plain request (403, JavaScript only, PDF): Firecrawl returns the rendered page as text.
    Needs FIRECRAWL_API_KEY in .env; returns None when unavailable or the page cannot be read."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    key = os.environ.get("FIRECRAWL_API_KEY")
    if not key:
        return None
    try:
        r = requests.post("https://api.firecrawl.dev/v1/scrape", headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                          json={"url": url, "formats": ["markdown"]}, timeout=120)
        if r.status_code != 200:
            return None
        return norm(re.sub(r"[#*_>|\[\]()]", " ", r.json().get("data", {}).get("markdown", "")))
    except (requests.RequestException, ValueError):
        return None


def fetch_text(url: str):
    try:
        r = requests.get(url, headers=UA, timeout=25)
        failure = "" if r.status_code == 200 and "pdf" not in r.headers.get("content-type", "").lower() else (f"HTTP {r.status_code}" if r.status_code != 200 else "PDF")
    except requests.RequestException as e:
        r, failure = None, f"{type(e).__name__}"
    if failure:
        text = firecrawl_text(url)
        return (text, "") if text else (None, failure)
    body = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", r.text)
    return norm(re.sub(r"<[^>]+>", " ", body)), ""


def aliases(company: str, company_map: dict) -> list[str]:
    names = {company, *company_map.get(company, {}).get("aliases", [])}
    out = set()
    for n in names:
        out.add(norm(n))
        out.add(norm(re.sub(r"\(.*?\)", "", n)).strip())
        out.add(norm(re.split(r"[ (/,&]", n)[0]))  # first word, e.g. 'Merck KGaA' -> 'merck'
    return sorted(a for a in out if len(a) >= 3)


NEAR = 60  # a place counts only if it appears within this many characters of the company name (or the page is the company's own site)


def near(text: str, names: list[str], pattern: str) -> str:
    """The text around the first spot where `pattern` (a place) appears within NEAR characters of a company name, else ''."""
    for pm in re.finditer(pattern, text):
        window = text[max(0, pm.start() - NEAR): pm.end() + NEAR]
        if any(re.search(r"\b" + re.escape(n) + r"\b", window) for n in names):
            return window
    return ""


def hq_near(text: str, names: list[str]) -> bool:
    """True if a headquarters word appears within 120 characters of the company name."""
    for hm in HQ_WORDS.finditer(text):
        window = text[max(0, hm.start() - 120): hm.end() + 120]
        if any(re.search(r"\b" + re.escape(n) + r"\b", window) for n in names):
            return True
    return False


def strict_window(url: str, text: str, names: list[str], place_re: str):
    """For the two list-style sources the plain 'near' test can pair a city with a neighbouring company, so use their exact patterns.
    Returns the matching text, '' when the pattern is not found, or None when the page is not one of these two (use the plain test)."""
    host = url.split("/")[2]
    nm = "|".join(re.escape(n) for n in names)
    if "interpharma.ch" in host:  # cards read '<Company> located in: <City> company: <Full name>'
        m = re.search(r"\b(?:" + nm + r")\b[^:]{0,50}located in: " + place_re + r"|located in: " + place_re + r" company: .{0,90}?\b(?:" + nm + r")\b", text)
        return m.group(0) if m else ""
    if "scienceindustries.ch" in host:  # member lists read '<Company>, <City>'; the city after the comma belongs to that company only
        m = re.search(r"\b(?:" + nm + r")\b[^,;]{0,45}, " + place_re, text)
        return m.group(0) if m else ""
    return None


def own_site(url: str, names: list[str]) -> bool:
    host = re.sub(r"[^a-z0-9]", "", re.sub(r"^https?://", "", url).split("/")[0].lower())
    return any(re.sub(r"[^a-z0-9]", "", n) in host for n in names if len(n) >= 4)


def validate(company: str, entry: dict, company_map: dict, manual: dict):
    man = manual.get(company)
    urls = [entry["source"], *entry.get("sources_extra", [])]  # a place is confirmed if ANY of these pages states it
    fetched = [fetch_text(u) for u in urls]
    texts = [(u, tx) for u, (tx, _) in zip(urls, fetched) if tx is not None]
    err = "; ".join(f"{u.split('/')[2]}: {e}" for u, (tx, e) in zip(urls, fetched) if tx is None)
    names = sorted(set(aliases(company, company_map)) | {norm(a) for a in entry.get("aliases_extra", [])})  # extra spellings the source pages use
    res = {"checked": str(date.today()), "source_read": bool(texts), "fetch_error": err, "sources_read": [u for u, _ in texts]}
    if not texts:
        if man:
            res.update(status="confirmed (manual)", places_confirmed=man["places_confirmed"], hq_confirmed=man.get("hq_confirmed", entry["kind"] == "HQ"), evidence=man["evidence"])
        else:
            res.update(status="could not fetch", places_confirmed=[], hq_confirmed=False, evidence="")
        return res
    mentions = lambda tx: any(re.search(r"\b" + re.escape(n) + r"\b", tx) for n in names)
    company_found = any(mentions(tx) for _, tx in texts)
    confirmed, evidence = [], ""
    for place in entry["places"]:
        pattern = SWISS_MARK.pattern if place == "Switzerland" else place_pattern(place)
        for u, tx in texts:
            strict = strict_window(u, tx, names, pattern) if place != "Switzerland" else None
            window = strict if strict is not None else near(tx, names, pattern)
            if strict is None and not window and mentions(tx) and own_site(u, names):  # the company's own page: the place only has to be on the page
                m = re.search(pattern, tx)
                window = tx[max(0, m.start() - 90): m.end() + 90] if m else ""
            if window:
                confirmed.append(place)
                evidence = evidence or f"[{u.split('/')[2]}] {window}"
                break
    hq_ok = entry["kind"] != "HQ" or any(hq_near(tx, names) for _, tx in texts)
    status = "confirmed" if company_found and confirmed and len(confirmed) == len(entry["places"]) else ("partly confirmed" if company_found and confirmed else "not found in source")
    if man and man.get("places_confirmed") and status != "confirmed":  # hand-checked evidence fills the gap
        res.update(status="confirmed (manual)", places_confirmed=man["places_confirmed"], hq_confirmed=man.get("hq_confirmed", hq_ok), evidence=man["evidence"])
        return res
    res.update(status=status, company_found=company_found, places_confirmed=confirmed, places_unconfirmed=[p for p in entry["places"] if p not in confirmed], hq_confirmed=hq_ok, evidence=evidence)
    if man and man.get("hq_evidence") and entry["kind"] == "HQ":  # a headquarters statement read by hand in the cited company page
        res.update(hq_confirmed=True, hq_evidence=man["hq_evidence"])
    return res


def main():
    data = json.load(open(FILE, encoding="utf-8"))
    company_map = json.load(open(SILVER / "company_gold_map.json", encoding="utf-8"))
    manual = json.load(open(MANUAL, encoding="utf-8")) if MANUAL.exists() else {}
    tally = {}
    for group in ("companies", "customers_not_on_map"):
        for company, entry in data[group].items():
            v = validate(company, entry, company_map, manual)
            entry["validation"] = v
            tally[v["status"]] = tally.get(v["status"], 0) + 1
            flag = {"confirmed": "OK ", "confirmed (manual)": "OK*"}.get(v["status"], "?? ")
            extra = "" if v["status"].startswith("confirmed") else f"  places not confirmed: {v.get('places_unconfirmed', entry['places'])}  {v['fetch_error']}"
            print(f"{flag} {company:42s} {v['status']:20s} {entry['places']}{extra}")
    json.dump(data, open(FILE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("\n", tally)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
