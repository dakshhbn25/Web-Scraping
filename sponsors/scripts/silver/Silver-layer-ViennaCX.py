import json
import re
import os
from bs4 import BeautifulSoup

BRONZE_PATH = "sponsors/data/bronze/viennacx.json"
DESCRIPTIONS_PATH = "sponsors/data/bronze/viennacx_descriptions.json"
SILVER_PATH = "sponsors/data/silver/viennacx.json"
EVENT_NAME = "ViennaCX"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_text(value):
    if not value:
        return value
    value = value.replace(" ", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def load_descriptions_lookup():
    data = load_json(DESCRIPTIONS_PATH)
    lookup = {}
    for entry in data["sponsors"]:
        key = entry["organization_name"].strip().lower()
        lookup[key] = {
            "description": normalize_text(entry.get("description")) or None,
            "website_url": entry.get("website_url") or None,
        }
    return lookup


def extract_sponsor_tiers(soup, descriptions_lookup):
    sponsors = []
    for section in soup.find_all("div", class_="section"):
        h3 = section.find("h3")
        boxes = section.find_all("div", class_=lambda c: c and "logo-box" in c)
        if not h3 or not boxes:
            continue

        tier = normalize_text(h3.get_text())

        for box in boxes:
            img = box.find("img")
            organization_name = normalize_text(img.get("alt")) if img else None
            logo_url = img.get("src") if img else None

            extra = descriptions_lookup.get((organization_name or "").strip().lower(), {})

            sponsors.append({
                "organization_name": organization_name,
                "sponsorship_tier": tier,
                "description": extra.get("description"),
                "website_url": extra.get("website_url"),
                "logo_url": logo_url,
            })

    return sponsors


def extract_sold_out_claim(soup):
    heading = next(
        (h for h in soup.find_all(["h2", "h3"]) if "sold out" in h.get_text(strip=True).lower()),
        None,
    )
    return normalize_text(heading.get_text()) if heading else None


def extract_stats(soup):
    heading = next(
        (h for h in soup.find_all(["h2", "h3"]) if "sold out" in h.get_text(strip=True).lower()),
        None,
    )
    if not heading:
        return []

    section = heading.find_parent("div")
    grid = section.find("div", class_=lambda c: c and "grid" in c) if section else None
    if not grid:
        return []

    stats = []
    for box in grid.find_all("div", recursive=False):
        h3 = box.find("h3")
        if h3:
            text = normalize_text(h3.get_text())
            if text:
                stats.append(text)
    return stats


def main():
    bronze = load_json(BRONZE_PATH)
    descriptions_lookup = load_descriptions_lookup()
    soup = BeautifulSoup(bronze.get("html") or "", "lxml")

    sponsors = extract_sponsor_tiers(soup, descriptions_lookup)
    for s in sponsors:
        s["event_name"] = EVENT_NAME
        s["source_urls"] = [bronze["metadata"].get("source_url")]
        s["scraped_at"] = bronze.get("scraped_at")

    record = {
        "event_name": EVENT_NAME,
        "sold_out_claim": extract_sold_out_claim(soup),
        "stats": extract_stats(soup),
        "sponsors": sponsors,
        "source_urls": [bronze["metadata"].get("source_url")],
        "scraped_at": bronze.get("scraped_at"),
    }

    with_description = sum(1 for s in sponsors if s["description"])
    print(f"{len(sponsors)} sponsors found")
    print(f"{with_description} / {len(sponsors)} have a description + website")
    tiers = sorted(set(s["sponsorship_tier"] for s in sponsors))
    print(f"tiers: {tiers}")

    os.makedirs("sponsors/data/silver", exist_ok=True)
    with open(SILVER_PATH, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    print(f"Wrote record -> {SILVER_PATH}")


if __name__ == "__main__":
    main()
