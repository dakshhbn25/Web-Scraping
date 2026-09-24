import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scripts.common import bronze_speaker_names, is_skipped, speaker_dir  # noqa: E402

GOLD_SPEAKERS_PATH = "speaker/data/gold/speakers.json"


def parse_experience(raw_experience):
    entries = []
    for e in raw_experience or []:
        entries.append({
            "title": (e.get("title") or {}).get("name"),
            "company": (e.get("company") or {}).get("name"),
            "company_industry": (e.get("company") or {}).get("industry"),
            "start_date": e.get("start_date"),
            "end_date": e.get("end_date"),
            "is_primary": e.get("is_primary", False),
        })
    return entries


def parse_education(raw_education):
    entries = []
    for e in raw_education or []:
        entries.append({
            "school": (e.get("school") or {}).get("name"),
            "majors": e.get("majors") or [],
            "degrees": e.get("degrees") or [],
            "start_date": e.get("start_date"),
            "end_date": e.get("end_date"),
        })
    return entries


def main():
    with open(GOLD_SPEAKERS_PATH, encoding="utf-8") as f:
        gold_speakers = json.load(f)

    speaker_names = {s["speaker_name"] for s in gold_speakers
                     if s.get("linkedin_url") and not is_skipped(s["speaker_name"])}
    speaker_names |= {n for n in bronze_speaker_names("linkedin_pdl.json") if not is_skipped(n)}

    processed = 0
    skipped = 0

    for name in sorted(speaker_names):
        bronze_path = f"{speaker_dir(name)}/data/bronze/linkedin_pdl.json"
        if not os.path.exists(bronze_path):
            continue

        with open(bronze_path, encoding="utf-8") as f:
            bronze = json.load(f)

        if bronze.get("status") != "success":
            skipped += 1
            continue

        raw = bronze.get("raw") or {}

        silver = {
            "record_id": bronze["record_id"],
            "speaker_name": bronze["speaker_name"],
            "linkedin_url": bronze["linkedin_url"],
            "likelihood": bronze.get("likelihood"),
            "full_name": raw.get("full_name"),
            "job_title": raw.get("job_title"),
            "industry": raw.get("industry"),
            "current_company": raw.get("job_company_name"),
            "current_company_website": raw.get("job_company_website"),
            "current_company_industry": raw.get("job_company_industry"),
            "location_country": raw.get("location_country"),
            "location_region": raw.get("location_region"),
            "location_locality": raw.get("location_locality"),
            "skills": raw.get("skills") or [],
            "interests": raw.get("interests") or [],
            "experience": parse_experience(raw.get("experience")),
            "education": parse_education(raw.get("education")),
        }

        out_dir = f"{speaker_dir(name)}/data/silver"
        os.makedirs(out_dir, exist_ok=True)
        with open(f"{out_dir}/linkedin_pdl.json", "w", encoding="utf-8") as f:
            json.dump(silver, f, indent=2, ensure_ascii=False)

        processed += 1
        print(f"parsed: {name} ({len(silver['skills'])} skills, {len(silver['experience'])} experience entries)")

    print(f"Done. {processed} silver PDL records written, {skipped} bronze records skipped (not success)")


if __name__ == "__main__":
    main()
