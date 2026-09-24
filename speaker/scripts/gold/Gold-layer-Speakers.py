import json
import os
import re

SILVER_FILES = {
    "Dubrovnik": "speaker/data/silver/dubrovnik.json",
    "Medical": "speaker/data/silver/medical.json",
    "ViennaCX": "speaker/data/silver/viennacx.json",
}

GOLD_PATH = "speaker/data/gold/speakers.json"

MIN_MATCH_LENGTH = 4  # guard against short abbreviations (e.g. "gsk") false-matching inside filenames


def load_silver(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_gold_record(speaker, event_key, index):
    silver_record_ref = f"{event_key.lower()}:{index}"
    record_id = f"speaker-{event_key.lower()}-{index:03d}"

    return {
        "record_id": record_id,
        "speaker_name": speaker["speaker_name"],
        "designation": speaker["designation"],
        "company": speaker["company"],
        "company_link": speaker.get("company_link"),
        "company_source": speaker.get("company_source"),
        "company_logo_filename": speaker.get("company_logo_filename"),
        "linkedin_url": speaker["linkedin_url"],
        "event_name": speaker["event_name"],
        "event_year": speaker["event_year"],
        "source_urls": speaker["source_urls"],
        "scraped_at": speaker["scraped_at"],
        "silver_record_ref": silver_record_ref,
    }


def normalize_for_match(value):
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def apply_filename_company_match(gold_records):
    """For records still missing a company, check if their logo's filename
    contains a company name we've already confirmed (via real alt text)
    somewhere else in the dataset. Only a known, previously-verified company
    can be matched this way -- never an arbitrary guess from the filename."""
    known_companies = {}  # normalized -> canonical display name
    for r in gold_records:
        if r["company_source"] == "alt_text" and r["company"]:
            norm = normalize_for_match(r["company"])
            if len(norm) >= MIN_MATCH_LENGTH:
                known_companies[norm] = r["company"]

    matched_count = 0
    for r in gold_records:
        if r["company"] is not None:
            continue
        filename_norm = normalize_for_match(r.get("company_logo_filename"))
        if not filename_norm:
            continue
        for known_norm, canonical_name in known_companies.items():
            if known_norm in filename_norm:
                r["company"] = canonical_name
                r["company_source"] = "filename_matched"
                matched_count += 1
                break

    return matched_count


def main():
    gold_records = []

    for event_key, path in SILVER_FILES.items():
        silver_speakers = load_silver(path)
        for i, speaker in enumerate(silver_speakers):
            gold_records.append(build_gold_record(speaker, event_key, i))

    matched = apply_filename_company_match(gold_records)
    print(f"{matched} additional companies recovered via filename cross-reference")

    for r in gold_records:
        r["missing_fields"] = [
            field for field in ("company", "linkedin_url", "event_year")
            if r.get(field) is None
        ]

    os.makedirs("speaker/data/gold", exist_ok=True)
    with open(GOLD_PATH, "w", encoding="utf-8") as f:
        json.dump(gold_records, f, indent=2, ensure_ascii=False)

    total = len(gold_records)
    with_missing = sum(1 for r in gold_records if r["missing_fields"])
    print(f"Wrote {total} gold speaker records -> {GOLD_PATH}")
    print(f"{with_missing} records have at least one missing field")


if __name__ == "__main__":
    main()
