"""Bronze layer for non-LinkedIn source material on speakers who have no
usable LinkedIn data (agenda speakers).

Unlike the LinkedIn bronze layers, sources here are a manually verified seed
list, not a generic per-speaker search -- these are heterogeneous personal
sites, employer bio pages, conference profiles, and press mentions, so each
one was checked by hand to confirm it's actually the same person (see
conversation history: a same-name horror novelist was caught and rejected
for the "Wayne Simmons" entry before this list was finalized).
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

# Verified non-LinkedIn sources per speaker. Each entry notes what confirmed
# the identity match, for anyone auditing this list later.
SOURCES = {
    "Caroline Chataing": {
        "verification": "The NEXT Medical Festival's own speaker announcement and a networkpharma.tv recording of the 'Plug in to Medical NEXT' panel name her as "
                         "'Global Scientific Communication Lead, RSV mAb at Sanofi'. A separate LinkedIn post by Benoit De Nayer says 'Caroline Chataing explains how "
                         "@Sanofi combines #CRM and #AI to boost HCP engagement' at the Digital Pharma Summit, which matches a Sanofi digital and medical role. "
                         "The only LinkedIn profile a search returns for the name is a different person (a Club Med lawyer, Caroline Chataing-Deguiraud) and was rejected.",
        "urls": [
            "https://networkpharma.tv/2026/02/04/plug-in-to-medical-next-navigating-complexity-driving-impact",
            "https://www.linkedin.com/posts/benoitdenayer_crm-ai-digitalpharma-activity-7311053707830280193-lYfB",
            "https://www.linkedin.com/posts/next-medical-festival_next-medical-festival-speaker-announcement-activity-7411765460444016640-sn_I",
        ],
    },
    "Sourav Ghosh": {
        "verification": "The NEXT recording of the 'Generalists, Specialists or Something In Between' panel and a MedAffairs Transformation (Zurich) event page both name him "
                         "'Head of Global Services, Medical & Scientific Affairs at Boehringer Ingelheim', matching the agenda designation exactly. "
                         "LinkedIn profiles and academic pages for other people named Sourav Ghosh (a Loughborough lecturer, a US professor) were rejected.",
        "urls": [
            "https://www.youtube.com/watch?v=svbgNlaZza8",
            "https://w.nextlevelpharma.com/events/medical-affairs-transformation-zurich",
        ],
    },
    "Tamara Krcmar": {
        "verification": "Healthware Group's LinkedIn post and webinar listing name her 'Director of Transversal Medical Communication for Cardiometabolic & Venous Diseases at Servier', "
                         "which matches the agenda designation. A NEXT interview video 'Speaking with Tamara Krcmar' discusses adherence and medical communication.",
        "urls": [
            "https://www.linkedin.com/posts/healthwaregroup_the-future-of-medical-affairs-at-servier-activity-7102604148700815361-SHu4",
            "https://www.linkedin.com/posts/francisnamouk_medicalaffairs-medcomms-medicaleducation-activity-7074705917048434688-3ghh",
            "https://www.youtube.com/watch?v=y6drc8Z2A5I",
        ],
    },
    "Bekir Basar Ozer": {
        "verification": "A LinkedIn speaker announcement by the organiser of the 2nd Pharma Commercial, Digital & SFE event introduces him as 'Regional Associate Medical Customer "
                         "Excellence Director, Medical & Digital Excellence from Shionogi Europe', and the NEXT recording of his session uses the same title; both match the agenda.",
        "urls": [
            "https://www.linkedin.com/posts/marxosmith_sfe-salesforceeffectiveness-commercial-activity-7226127334993461248-o7tJ",
            "https://www.youtube.com/watch?v=YW6_ZOoGQjQ",
        ],
    },
}


def bronze_path_for(speaker_name):
    return f"{speaker_dir(speaker_name)}/data/bronze/alt_sources.json"


def already_scraped(speaker_name):
    path = bronze_path_for(speaker_name)
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        entry = json.load(f)
    return entry.get("status") == "success"


def scrape_one(speaker_name, config):
    entry = {
        "speaker_name": speaker_name,
        "verification": config["verification"],
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "pages": [],
    }

    success_count = 0
    for url in config["urls"]:
        try:
            result = client.extract(urls=[url], extract_depth="advanced", format="markdown")
            if result.get("results"):
                page = result["results"][0]
                entry["pages"].append({
                    "url": url,
                    "title": page.get("title"),
                    "raw_content": page.get("raw_content"),
                    "status": "success",
                })
                success_count += 1
            else:
                entry["pages"].append({"url": url, "status": "failed", "error": str(result.get("failed_results"))})
        except Exception as e:
            entry["pages"].append({"url": url, "status": "failed", "error": str(e)})
        time.sleep(REQUEST_DELAY_SECONDS)

    entry["status"] = "success" if success_count > 0 else "failed"
    return entry


def main():
    pending = [name for name in SOURCES if not already_scraped(name)]
    print(f"{len(SOURCES)} speakers configured, {len(pending)} not yet scraped")

    for i, name in enumerate(pending):
        entry = scrape_one(name, SOURCES[name])

        out_dir = f"{speaker_dir(name)}/data/bronze"
        os.makedirs(out_dir, exist_ok=True)
        with open(f"{out_dir}/alt_sources.json", "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)

        ok = sum(1 for p in entry["pages"] if p["status"] == "success")
        print(f"[{i+1}/{len(pending)}] {name}: {ok}/{len(entry['pages'])} pages scraped")

    print("Done.")


if __name__ == "__main__":
    main()
