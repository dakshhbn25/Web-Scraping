import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scripts.common import bronze_speaker_names, is_skipped, speaker_dir  # noqa: E402

GOLD_SPEAKERS_PATH = "speaker/data/gold/speakers.json"


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    with open(GOLD_SPEAKERS_PATH, encoding="utf-8") as f:
        gold_speakers = json.load(f)

    by_name = {s["speaker_name"]: s for s in gold_speakers
               if s.get("linkedin_url") and not is_skipped(s["speaker_name"])}

    # Speakers recovered via manually-researched URLs (no linkedin_url in the
    # master roster, so they're not in by_name) -- still process them if a
    # bronze file exists, just without roster fields like designation/event.
    all_names = sorted(set(by_name) | {n for n in bronze_speaker_names() if not is_skipped(n)})

    written = 0
    skipped = 0

    for name in all_names:
        speaker = by_name.get(name, {})
        tavily = load_json(f"{speaker_dir(name)}/data/silver/linkedin.json")
        pdl = load_json(f"{speaker_dir(name)}/data/silver/linkedin_pdl.json")

        if tavily is None and pdl is None:
            continue

        tavily = tavily or {}
        pdl = pdl or {}
        linkedin_url = speaker.get("linkedin_url") or tavily.get("linkedin_url")

        gold_record = {
            "record_id": speaker.get("record_id"),
            "speaker_name": name,
            "designation": speaker.get("designation"),
            "company": speaker.get("company"),
            "event_name": speaker.get("event_name"),
            "event_year": speaker.get("event_year"),
            "linkedin_url": linkedin_url,
            "recovered_via_manual_research": name not in by_name,

            # From Tavily (public-page extraction): bio preview, social activity
            "linkedin_headline_company": tavily.get("headline_company"),
            "linkedin_location": tavily.get("location"),
            "linkedin_connections": tavily.get("connections"),
            "linkedin_followers": tavily.get("followers"),
            "linkedin_about": tavily.get("about"),
            "linkedin_about_en": tavily.get("about_en"),
            "linkedin_languages": tavily.get("languages"),
            "linkedin_languages_en": tavily.get("languages_en"),
            "linkedin_certifications": tavily.get("certifications"),
            "linkedin_certifications_en": tavily.get("certifications_en"),
            "linkedin_honors_and_awards": tavily.get("honors_and_awards"),
            "linkedin_honors_and_awards_en": tavily.get("honors_and_awards_en"),
            "linkedin_activity": tavily.get("activity"),
            "linkedin_people_also_viewed": tavily.get("people_also_viewed"),

            # From PDL (licensed enrichment database): full work/education history, skills
            "linkedin_industry": pdl.get("industry"),
            "linkedin_current_company": pdl.get("current_company") or tavily.get("headline_company"),
            "linkedin_current_company_website": pdl.get("current_company_website"),
            "linkedin_skills": pdl.get("skills") or [],

            # Prefer PDL's structured experience/education; fall back to Tavily's
            # (which is often redacted/empty since it comes from an unauthenticated view)
            "linkedin_experience": pdl.get("experience") or tavily.get("experience") or [],
            "linkedin_education": pdl.get("education") or tavily.get("education"),

            "data_sources": {
                "tavily": bool(tavily),
                "pdl": bool(pdl),
            },
        }
        gold_record["missing_fields"] = [
            field for field in ("linkedin_current_company", "linkedin_about", "linkedin_skills", "linkedin_experience")
            if not gold_record.get(field)
        ]

        out_dir = f"{speaker_dir(name)}/data/gold"
        os.makedirs(out_dir, exist_ok=True)
        with open(f"{out_dir}/linkedin.json", "w", encoding="utf-8") as f:
            json.dump(gold_record, f, indent=2, ensure_ascii=False)

        written += 1
        print(f"gold: {name}")

    print(f"Done. {written} gold LinkedIn records written")


if __name__ == "__main__":
    main()
