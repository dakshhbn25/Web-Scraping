import json
import os

SILVER_FILES = {
    "Dubrovnik": "sponsors/data/silver/dubrovnik.json",
    "Medical": "sponsors/data/silver/medical.json",
    "ViennaCX": "sponsors/data/silver/viennacx.json",
}

SPONSORS_GOLD_PATH = "sponsors/data/gold/sponsors.json"
STATS_GOLD_PATH = "sponsors/data/gold/exhibition_stats.json"


def load_silver(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_sponsor_record(sponsor, event_key, index):
    missing_fields = [
        field for field in ("organization_name", "sponsorship_tier", "description", "website_url", "logo_url")
        if not sponsor.get(field)
    ]
    return {
        "record_id": f"sponsor-{event_key.lower()}-{index:03d}",
        "organization_name": sponsor["organization_name"],
        "sponsorship_tier": sponsor["sponsorship_tier"],
        "description": sponsor["description"],
        "website_url": sponsor["website_url"],
        "logo_url": sponsor["logo_url"],
        "event_name": sponsor["event_name"],
        "source_urls": sponsor["source_urls"],
        "scraped_at": sponsor["scraped_at"],
        "missing_fields": missing_fields,
    }


def build_stats_record(silver_record, event_key):
    missing_fields = []
    if not silver_record.get("sold_out_claim"):
        missing_fields.append("sold_out_claim")
    if not silver_record.get("stats"):
        missing_fields.append("stats")

    return {
        "record_id": f"exhibition-stats-{event_key.lower()}",
        "event_name": silver_record["event_name"],
        "sold_out_claim": silver_record["sold_out_claim"],
        "stats": silver_record["stats"],
        "source_urls": silver_record["source_urls"],
        "scraped_at": silver_record["scraped_at"],
        "missing_fields": missing_fields,
    }


def main():
    sponsor_records = []
    stats_records = []

    for event_key, path in SILVER_FILES.items():
        silver_record = load_silver(path)

        for i, sponsor in enumerate(silver_record["sponsors"]):
            sponsor_records.append(build_sponsor_record(sponsor, event_key, i))

        stats_records.append(build_stats_record(silver_record, event_key))

    os.makedirs("sponsors/data/gold", exist_ok=True)

    with open(SPONSORS_GOLD_PATH, "w", encoding="utf-8") as f:
        json.dump(sponsor_records, f, indent=2, ensure_ascii=False)

    with open(STATS_GOLD_PATH, "w", encoding="utf-8") as f:
        json.dump(stats_records, f, indent=2, ensure_ascii=False)

    total = len(sponsor_records)
    with_missing = sum(1 for r in sponsor_records if r["missing_fields"])
    print(f"Wrote {total} gold sponsor records -> {SPONSORS_GOLD_PATH}")
    print(f"{with_missing} sponsor records have at least one missing field")
    print(f"Wrote {len(stats_records)} gold exhibition-stats records -> {STATS_GOLD_PATH}")


if __name__ == "__main__":
    main()
