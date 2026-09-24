import json
import os

SILVER_FILES = {
    "Dubrovnik": "agenda/data/silver/dubrovnik_agenda.json",
    "Medical": "agenda/data/silver/medical_agenda.json",
    "ViennaCX": "agenda/data/silver/viennacx_agenda.json",
}

GOLD_PATH = "agenda/data/gold/sessions.json"


def load_silver(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_gold_record(session, event_key, index):
    silver_record_ref = f"{event_key.lower()}:{index}"
    record_id = f"session-{event_key.lower()}-{index:03d}"

    missing_fields = [
        field for field in ("start_time", "end_time", "track")
        if session.get(field) is None
    ]
    if not session.get("speakers"):
        missing_fields.append("speakers")

    return {
        "record_id": record_id,
        "session_title": session["session_title"],
        "event_name": session["event_name"],
        "day": session["day"],
        "start_time": session["start_time"],
        "end_time": session["end_time"],
        "track": session["track"],
        "speakers": session["speakers"],
        "source_urls": session["source_urls"],
        "scraped_at": session["scraped_at"],
        "silver_record_ref": silver_record_ref,
        "missing_fields": missing_fields,
    }


def main():
    gold_records = []

    for event_key, path in SILVER_FILES.items():
        silver_sessions = load_silver(path)
        for i, session in enumerate(silver_sessions):
            gold_records.append(build_gold_record(session, event_key, i))

    os.makedirs("agenda/data/gold", exist_ok=True)
    with open(GOLD_PATH, "w", encoding="utf-8") as f:
        json.dump(gold_records, f, indent=2, ensure_ascii=False)

    total = len(gold_records)
    with_missing = sum(1 for r in gold_records if r["missing_fields"])
    no_speakers = sum(1 for r in gold_records if not r["speakers"])
    print(f"Wrote {total} gold session records -> {GOLD_PATH}")
    print(f"{with_missing} records have at least one missing field")
    print(f"{no_speakers} sessions have zero speakers listed")


if __name__ == "__main__":
    main()