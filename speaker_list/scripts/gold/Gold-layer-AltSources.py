import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scripts.common import speaker_dir  # noqa: E402

GOLD_SPEAKERS_PATH = "speaker/data/gold/speakers.json"


def linkedin_status_for(name):
    """These alt sources supplement whatever LinkedIn data exists (which may
    be full, partial, or none) -- report which, rather than assuming none."""
    path = f"{speaker_dir(name)}/data/gold/linkedin.json"
    if not os.path.exists(path):
        return "no LinkedIn data (unreachable via Tavily or PDL)"
    linkedin = json.load(open(path, encoding="utf-8"))
    missing = [f.replace("linkedin_", "") for f in
               ("linkedin_experience", "linkedin_skills", "linkedin_education", "linkedin_current_company")
               if not linkedin.get(f)]
    return f"LinkedIn data present but missing: {', '.join(missing)}" if missing else "LinkedIn data present"


def main():
    master = {s["speaker_name"]: s for s in json.load(open(GOLD_SPEAKERS_PATH, encoding="utf-8"))}

    written = 0
    for silver_path in glob.glob("speaker_list/*/data/silver/alt_sources.json"):
        with open(silver_path, encoding="utf-8") as f:
            silver = json.load(f)
        name = silver["speaker_name"]
        roster = master.get(name, {})

        gold_record = {
            "speaker_name": name,
            "designation": roster.get("designation"),
            "company": roster.get("company"),
            "event_name": roster.get("event_name"),
            "event_year": roster.get("event_year"),
            "linkedin_status": linkedin_status_for(name),
            "identity_verification": silver["verification"],
            "sources": silver["sources"],
        }

        out_dir = f"{speaker_dir(name)}/data/gold"
        os.makedirs(out_dir, exist_ok=True)
        with open(f"{out_dir}/alt_sources.json", "w", encoding="utf-8") as f:
            json.dump(gold_record, f, indent=2, ensure_ascii=False)
        written += 1
        print(f"gold: {name} ({len(gold_record['sources'])} sources)")

    print(f"Done. {written} gold alt-source records written")


if __name__ == "__main__":
    main()
