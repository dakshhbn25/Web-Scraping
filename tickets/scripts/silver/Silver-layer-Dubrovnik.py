import json
import re
import os
from bs4 import BeautifulSoup

BRONZE_PATH = "tickets/data/bronze/dubrovnik.json"
SILVER_PATH = "tickets/data/silver/dubrovnik.json"
EVENT_NAME = "Dubrovnik"


def load_bronze(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_text(value):
    if not value:
        return value
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


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


def extract_attendee_companies(soup):
    heading = next(
        (h for h in soup.find_all(["h2", "h3"]) if "who attended" in h.get_text(strip=True).lower()),
        None,
    )
    if not heading:
        return []

    section = heading.find_parent("div").parent
    seen = set()
    companies = []
    for img in section.find_all("img"):
        alt = normalize_text(img.get("alt"))
        src = img.get("src")
        if not alt or not src:
            continue
        key = (alt.lower(), src)
        if key in seen:
            continue
        seen.add(key)
        companies.append({"company_name": alt, "logo_url": src})
    return companies


def main():
    bronze = load_bronze(BRONZE_PATH)
    soup = BeautifulSoup(bronze.get("html") or "", "lxml")

    record = {
        "record_id": f"tickets-{EVENT_NAME.lower()}",
        "event_name": EVENT_NAME,
        "sold_out_claim": extract_sold_out_claim(soup),
        "stats": extract_stats(soup),
        "attendee_companies": extract_attendee_companies(soup),
        "source_urls": [bronze["metadata"].get("source_url")],
        "scraped_at": bronze.get("scraped_at"),
    }

    print(f"sold_out_claim: {record['sold_out_claim']}")
    print(f"stats: {record['stats']}")
    print(f"attendee_companies: {len(record['attendee_companies'])} unique companies")

    os.makedirs("tickets/data/silver", exist_ok=True)
    with open(SILVER_PATH, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    print(f"Wrote record -> {SILVER_PATH}")


if __name__ == "__main__":
    main()