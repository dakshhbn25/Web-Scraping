import json
import os
import sys
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from peopledatalabs import PDLPY

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scripts.common import is_skipped, speaker_dir  # noqa: E402

load_dotenv()


def available_api_keys():
    """PDL_API_KEY, PDL_API_KEY1, PDL_API_KEY2, ... in order. Each free-tier key
    caps at 100 matches/month, so the run rotates to the next key when one is spent."""
    keys = [os.getenv("PDL_API_KEY")]
    i = 1
    while os.getenv(f"PDL_API_KEY{i}"):
        keys.append(os.getenv(f"PDL_API_KEY{i}"))
        i += 1
    return [k for k in keys if k]


API_KEYS = available_api_keys()

GOLD_SPEAKERS_PATH = "speaker/data/gold/speakers.json"

PILOT_BATCH_SIZE = 300  # covers all 223 candidates; free tier (100 credits/month) will cap successes
REQUEST_DELAY_SECONDS = 1
QUOTA_STATUS_CODES = {402, 429}


def load_speakers():
    with open(GOLD_SPEAKERS_PATH, encoding="utf-8") as f:
        return json.load(f)


def bronze_path_for(speaker_name):
    return f"{speaker_dir(speaker_name)}/data/bronze/linkedin_pdl.json"


def already_scraped(speaker_name):
    path = bronze_path_for(speaker_name)
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        entry = json.load(f)
    return entry.get("status") == "success"


def enrich_one(speaker, client):
    linkedin_url = speaker["linkedin_url"]
    entry = {
        "record_id": speaker["record_id"],
        "speaker_name": speaker.get("speaker_name"),
        "event_name": speaker.get("event_name"),
        "linkedin_url": linkedin_url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        resp = client.person.enrichment(profile=linkedin_url)
        if resp.status_code == 200:
            body = resp.json()
            entry["likelihood"] = body.get("likelihood")
            entry["raw"] = body.get("data")
            entry["status"] = "success"
        elif resp.status_code == 404:
            entry["status"] = "not_found"
            entry["error"] = "PDL has no match for this profile"
        elif resp.status_code in QUOTA_STATUS_CODES:
            entry["status"] = "quota_exceeded"
            entry["error"] = f"HTTP {resp.status_code}: {resp.text[:300]}"
        else:
            entry["status"] = "failed"
            entry["error"] = f"HTTP {resp.status_code}: {resp.text[:300]}"
    except Exception as e:
        entry["status"] = "failed"
        entry["error"] = str(e)

    return entry


def has_tavily_data(speaker_name):
    path = f"{speaker_dir(speaker_name)}/data/bronze/linkedin.json"
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("status") == "success"


def main():
    if not API_KEYS:
        sys.exit("No PDL API key found. Set PDL_API_KEY (and optionally PDL_API_KEY1, ...) in .env")

    speakers = load_speakers()
    candidates = [s for s in speakers if s.get("linkedin_url") and not is_skipped(s["speaker_name"])]

    seen = set()
    pending = []
    for s in candidates:
        name = s["speaker_name"]
        if name in seen or already_scraped(name):
            continue
        seen.add(name)
        pending.append(s)

    # Speakers with no Tavily data either have nothing at all -- enrich them first,
    # since credits may run out before the whole queue is processed.
    pending.sort(key=lambda s: has_tavily_data(s["speaker_name"]))
    batch = pending[:PILOT_BATCH_SIZE]

    no_data_first = sum(1 for s in batch if not has_tavily_data(s["speaker_name"]))
    print(f"{len(candidates)} speaker records, {len(pending)} unique speakers still need PDL enrichment")
    print(f"{len(API_KEYS)} API key(s) available; prioritising {no_data_first} speaker(s) who currently have no data at all")
    print("Note: PDL only bills for successful matches (status 200) -- not_found/failed lookups are free.")

    key_index = 0
    client = PDLPY(api_key=API_KEYS[key_index])

    success_count = 0
    not_found_count = 0
    failed_count = 0
    exhausted = False

    for i, speaker in enumerate(batch):
        entry = enrich_one(speaker, client)

        # A spent key means this speaker wasn't actually looked up -- rotate and retry them.
        while entry["status"] == "quota_exceeded" and key_index + 1 < len(API_KEYS):
            key_index += 1
            print(f"    key #{key_index} exhausted, switching to key #{key_index + 1}")
            client = PDLPY(api_key=API_KEYS[key_index])
            entry = enrich_one(speaker, client)

        if entry["status"] == "quota_exceeded":
            print(f"[{i+1}/{len(batch)}] all {len(API_KEYS)} key(s) exhausted -- stopping.")
            print(f"{len(batch) - i} speaker(s) left for a future run.")
            exhausted = True
            break

        out_dir = f"{speaker_dir(speaker['speaker_name'])}/data/bronze"
        os.makedirs(out_dir, exist_ok=True)
        with open(f"{out_dir}/linkedin_pdl.json", "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)

        status = entry["status"]
        if status == "success":
            success_count += 1
            print(f"[{i+1}/{len(batch)}] success: {speaker.get('speaker_name')} (likelihood {entry.get('likelihood')})")
        elif status == "not_found":
            not_found_count += 1
            print(f"[{i+1}/{len(batch)}] not found: {speaker.get('speaker_name')}")
        else:
            failed_count += 1
            print(f"[{i+1}/{len(batch)}] failed: {speaker.get('speaker_name')} - {entry.get('error')}")

        if i < len(batch) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)

    ran = success_count + not_found_count + failed_count
    print(f"Done. {success_count} success, {not_found_count} not found, {failed_count} failed, {ran} processed this run"
          + (" (stopped early: out of credits)" if exhausted else ""))


if __name__ == "__main__":
    main()
