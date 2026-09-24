import json
import os
import sys
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from tavily import TavilyClient

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scripts.common import is_skipped, slugify_name, speaker_dir  # noqa: E402

load_dotenv()

client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

GOLD_SPEAKERS_PATH = "speaker/data/gold/speakers.json"

PILOT_BATCH_SIZE = 300  # covers all 223 candidates in one run
REQUEST_DELAY_SECONDS = 2


def load_speakers():
    with open(GOLD_SPEAKERS_PATH, encoding="utf-8") as f:
        return json.load(f)


def bronze_path_for(speaker_name):
    return f"{speaker_dir(speaker_name)}/data/bronze/linkedin.json"


def already_scraped(speaker_name):
    path = bronze_path_for(speaker_name)
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        entry = json.load(f)
    return entry.get("status") == "success"


def scrape_one(speaker):
    linkedin_url = speaker["linkedin_url"]
    entry = {
        "record_id": speaker["record_id"],
        "speaker_name": speaker.get("speaker_name"),
        "event_name": speaker.get("event_name"),
        "linkedin_url": linkedin_url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result = client.extract(
            urls=[linkedin_url],
            extract_depth="advanced",
            format="markdown",
        )
        if result.get("results"):
            entry["raw_content"] = result["results"][0].get("raw_content")
            entry["title"] = result["results"][0].get("title")
            entry["status"] = "success"
        else:
            entry["status"] = "failed"
            entry["error"] = result.get("failed_results") or "no results returned"
    except Exception as e:
        entry["status"] = "failed"
        entry["error"] = str(e)

    return entry


def main():
    speakers = load_speakers()
    candidates = [s for s in speakers if s.get("linkedin_url") and not is_skipped(s["speaker_name"])]
    pending = [s for s in candidates if not already_scraped(s["speaker_name"])]
    batch = pending[:PILOT_BATCH_SIZE]

    print(f"{len(candidates)} speakers have a linkedin_url, {len(pending)} not yet scraped, running pilot batch of {len(batch)}")

    success_count = 0
    failed_count = 0

    for i, speaker in enumerate(batch):
        entry = scrape_one(speaker)

        out_dir = f"{speaker_dir(speaker['speaker_name'])}/data/bronze"
        os.makedirs(out_dir, exist_ok=True)
        with open(f"{out_dir}/linkedin.json", "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)

        if entry["status"] == "success":
            success_count += 1
            print(f"[{i+1}/{len(batch)}] success: {speaker.get('speaker_name')} ({speaker.get('event_name')})")
        else:
            failed_count += 1
            print(f"[{i+1}/{len(batch)}] failed: {speaker.get('speaker_name')} ({speaker.get('event_name')}) - {entry.get('error')}")

        if i < len(batch) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)

    print(f"Done. {success_count} success, {failed_count} failed, {len(batch)} total this run")


if __name__ == "__main__":
    main()
