"""Bronze layer for speakers who have NO linkedin_url in the master roster
(speaker/data/gold/speakers.json) at all -- the standard Bronze-layer-LinkedIn
scripts can't reach them since they filter on that field.

Each URL here was found via search and verified by re-extracting the page
and confirming the employer named on it matches the roster's company field
-- not just a search-result snippet match. See the note per person for what
confirmed it.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from tavily import TavilyClient

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scripts.common import speaker_dir  # noqa: E402

load_dotenv()

client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

REQUEST_DELAY_SECONDS = 2

RECOVERED_URLS = {
    "Ashvin Dharmavaram Bhogendra": {
        "url": "https://www.linkedin.com/in/ashvin-bhogendra-73b74736",
        "verification": "Page content itself names 'Axtria - Ingenious Insights' -- exact match "
                         "to roster company 'axtria'.",
    },
    "Shivani Parikh": {
        "url": "https://www.linkedin.com/in/shivani-parikh-3171472b/",
        "verification": "Page content itself names 'Astellas Pharma' -- exact match to roster "
                         "company 'astellas.com', and location (London) matches a content/channel role.",
    },
    "Vangelis Oikonomou": {
        "url": "https://www.linkedin.com/in/vangelisoikonomou/",
        "verification": "Page content itself names Novartis-consistent commercial/launch strategy "
                         "role, Basel-based -- matches roster 'Director, International Commercial "
                         "Excellence' at Novartis.",
    },
    "Wayne Simmons": {
        "url": "https://www.linkedin.com/in/wayne-simmons-cxedna/",
        "verification": "CCXP-certified, 'The Customer Excellence AGENCY' -- matches roster "
                         "designation 'Founder & Author' exactly (he founded this agency). An "
                         "initial search had matched a same-name horror novelist; rejected after "
                         "checking this page's actual content.",
    },
}


def bronze_path_for(speaker_name):
    return f"{speaker_dir(speaker_name)}/data/bronze/linkedin.json"


def already_scraped(speaker_name):
    path = bronze_path_for(speaker_name)
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("status") == "success"


def scrape_one(speaker_name, config):
    entry = {
        "record_id": None,  # not in the master roster's record set
        "speaker_name": speaker_name,
        "event_name": None,
        "linkedin_url": config["url"],
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "recovery_verification": config["verification"],
    }

    try:
        result = client.extract(urls=[config["url"]], extract_depth="advanced", format="markdown")
        if result.get("results"):
            entry["raw_content"] = result["results"][0].get("raw_content")
            entry["title"] = result["results"][0].get("title")
            entry["status"] = "success"
        else:
            entry["status"] = "failed"
            entry["error"] = str(result.get("failed_results"))
    except Exception as e:
        entry["status"] = "failed"
        entry["error"] = str(e)

    return entry


def main():
    pending = [name for name in RECOVERED_URLS if not already_scraped(name)]
    print(f"{len(RECOVERED_URLS)} recovered URLs configured, {len(pending)} not yet scraped")

    for i, name in enumerate(pending):
        entry = scrape_one(name, RECOVERED_URLS[name])

        out_dir = f"{speaker_dir(name)}/data/bronze"
        os.makedirs(out_dir, exist_ok=True)
        with open(f"{out_dir}/linkedin.json", "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)

        print(f"[{i+1}/{len(pending)}] {name}: {entry['status']}")
        if i < len(pending) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)

    print("Done.")


if __name__ == "__main__":
    main()
