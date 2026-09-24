import json
import os

SILVER_FILES = {
    "Dubrovnik": "tickets/data/silver/dubrovnik.json",
    "Medical": "tickets/data/silver/medical.json",
    "ViennaCX": "tickets/data/silver/viennacx.json",
}

GOLD_PATH = "tickets/data/gold/tickets.json"


def load_silver(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_gold_record(record):
    missing_fields = []
    if not record.get("sold_out_claim"):
        missing_fields.append("sold_out_claim")
    if not record.get("stats"):
        missing_fields.append("stats")
    if not record.get("attendee_companies"):
        missing_fields.append("attendee_companies")

    record = dict(record)
    record["missing_fields"] = missing_fields
    return record


def main():
    gold_records = []

    for event_key, path in SILVER_FILES.items():
        silver_record = load_silver(path)
        gold_records.append(build_gold_record(silver_record))

    os.makedirs("tickets/data/gold", exist_ok=True)
    with open(GOLD_PATH, "w", encoding="utf-8") as f:
        json.dump(gold_records, f, indent=2, ensure_ascii=False)

    total = len(gold_records)
    with_missing = sum(1 for r in gold_records if r["missing_fields"])
    print(f"Wrote {total} gold ticket records -> {GOLD_PATH}")
    for r in gold_records:
        print(f"  {r['event_name']}: {r['missing_fields'] or 'complete'}")


if __name__ == "__main__":
    main()