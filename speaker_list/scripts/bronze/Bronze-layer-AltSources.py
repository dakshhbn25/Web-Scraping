"""Bronze layer for non-LinkedIn source material on speakers who have no
usable LinkedIn data (see speaker_list's SKIP_SPEAKERS / no-data list).

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
    "Darren Feenan": {
        "verification": "CXPA (Customer Experience Professional Association) member directory page "
                         "names him 'Darren Feenan, CCXP -- Pfizer', with a detailed first-person "
                         "career narrative ('nearly 30 years at Pfizer'). A PharmExec interview "
                         "separately names him by full name and title ('Darren Feenan, global "
                         "experience lead, customer-facing digital at Pfizer'). Matches roster "
                         "designation ('Senior customer experience... leader') and his own LinkedIn "
                         "activity post mentioning a 30-year Pfizer career -- now at Kanga Health.",
        "urls": [
            "https://cxpaglobal.org/directory/darren-feenan",
            "https://www.pharmexec.com/view/capturing-consent-connecting-hcps-with-scientific-content",
        ],
    },
    "Lois-An Gregory": {
        "verification": "Bio explicitly names her Google role: 'Strategy and Insight Lead, "
                         "Health & Wellness, Google' -- matches roster designation/company exactly.",
        "urls": [
            "https://www.pharmabrands.ca/rcindi",
            "https://solli.global/solli-hub/lois-an-gregory-solli-sessions-season-4",
            "https://thedhcgroup.com/pharmaforward2025",
        ],
    },
    "Leann Pezdirtz": {
        "verification": "HBA Luminaries award listing and MSL Journal byline both name her at "
                         "Boehringer Ingelheim in a medical/field-based-medicine role, matching "
                         "roster designation 'Vice President, Medicine Excellence' at the same employer.",
        "urls": [
            "https://themsljournal.com/article/new-diversity-and-inclusion-initiative",
            "https://hbanet.org/our-impact/hba-awards/hba-luminaries/previous-hba-luminaries/2019-hba-luminaries",
        ],
    },
    "Wayne Simmons": {
        "verification": "Confirmed via direct search for 'Wayne Simmons NEXT Pharma Summit ViennaCX' "
                         "-- CCXP-certified, Global Customer Excellence Lead at Pfizer, co-author of "
                         "'The Customer Excellence Enterprise'. An initial search had matched a "
                         "same-name horror novelist; that was rejected after this direct check.",
        "urls": [
            "https://thebusinessshowus.com/speakers/wayne-simmons",
            "https://www.porchlightbooks.com/products/customer-excellence-enterprise-wayne-simmons-9781394253685",
        ],
    },
    "Vangelis Oikonomou": {
        "verification": "Business-school alumni bio names him at Novartis Switzerland; roster has "
                         "him as 'Director, International Commercial Excellence' at Novartis -- same "
                         "employer, consistent career progression from the 2009 profile.",
        "urls": [
            "https://imba.aueb.gr/newsletterpost/alumni-profile-vangelis-oikonomou-region-europe-brand-manager-at-novartis-switzerland-2009-graduate",
        ],
    },
    "Debbie Young": {
        "verification": "Podcast interview page content confirms 'Otsuka' by name; roster has her as "
                         "'Multichannel Strategy and Customer Insights Director' at otsuka-europe.com.",
        "urls": [
            "https://www.thisgirlkam.com/debbie-young",
            "https://www.veeva.com/customer-stories/otsukas-launch-90-days-to-personalize-customer-content-using-modular",
        ],
    },
    "Derek Choy": {
        "verification": "PharmaForceIQ's own site and Fierce Pharma both name him 'Head of Product' "
                         "there -- matches roster company 'PFIQ' exactly (PharmaForceIQ's short name).",
        "urls": [
            "https://pharmaforceiq.com/breaking-down-silos-how-pharmaforceiq-aktana-finally-unifies-brand-and-field",
            "https://www.fiercepharma.com/company/pharmaforceiq-llc",
        ],
    },
    "Eric Alsac": {
        "verification": "Equilar executive-bio database page content confirms 'Norgine' by name -- "
                         "matches roster company exactly. Notes a prior title (BU Head Consumer "
                         "Health) vs roster's current VP/Commercial Operations -- plausible career "
                         "progression at the same employer, not a different person.",
        "urls": [
            "https://people.equilar.com/bio/person/eric-alsac-norgine-pharmaceuticals-limited/43076323",
        ],
    },
    "Laura Avanzo Leeke": {
        "verification": "Official DIA Global conference speaker bio names her 'Global Medical "
                         "Information Manager, Recordati Rare Disease' -- matches roster exactly.",
        "urls": [
            "https://www.diaglobal.org/en/conference-listing/meetings/2025/10/medical-information-communications-conference/speakers",
            "https://www.avayl.tech/agenda-and-speakers",
        ],
    },
    "Lutgarde Allard": {
        "verification": "European Myasthenia Gravis Association's own contact page and the European "
                         "Brain Council's event page both name her President/Treasurer of EuMGA -- "
                         "matches roster company 'eumga' and designation exactly.",
        "urls": [
            "https://ern-euro-nmd.eu/contact/68477-2",
            "https://www.braincouncil.eu/rare-disease-day-2025",
        ],
    },
    "Mark Meyling": {
        "verification": "Event bio page content names him 'Director, Sales, Medical Education at "
                         "Wiley' -- an exact string match to the roster designation and company.",
        "urls": [
            "https://mymedicalaffairs.com/event/squeezing-the-medical-affairs-lemon",
        ],
    },
    "Paméla Graas": {
        "verification": "Industry blog quote and event listing both name her at Takeda in a Global "
                         "Medical Affairs / Medical Capability role -- matches roster company exactly.",
        "urls": [
            "https://medicalaffairsvalue.com/blog/what-hcps-want-from-msls",
            "https://w.nextlevelpharma.com/events/medical-affairs-transformation-zurich",
        ],
    },
    "Patrick Markt-Niederreiter": {
        "verification": "His own company's About Us page -- 'Dr. Patrick Markt-Niederreiter' -- "
                         "matches roster designation 'Co-Founder' at 'ceel-ai' exactly.",
        "urls": [
            "https://www.ceel.ai/about-us",
        ],
    },
    "Paul Tunnah": {
        "verification": "CCI Life Sciences' own site and pharmaphorum (which he founded) both "
                         "confirm his identity and pharma-industry background; roster designation "
                         "'Pharma Expert' has no listed company, consistent with an independent "
                         "consultant/adviser role.",
        "urls": [
            "https://www.ccilifesciences.com",
            "https://pharmaphorum.com/author/paulpharmaphorum-com",
        ],
    },
    "Pierre Metrailler": {
        "verification": "Informa Connect and Fierce Pharma Week speaker bios both confirm 'CEO' at "
                         "SpotMe/Onomi -- matches roster designation 'CEO' at 'onomi.io' exactly.",
        "urls": [
            "https://informaconnect.com/pharma-forum-emea/speakers/pierre-metrailler",
            "https://www.fiercepharmaweek.com/event/contact/pierre-metrailler",
        ],
    },
    "Stefani Klaskow": {
        "verification": "Two independent conference speaker-bio pages (DigiPharma, HITLAB) both name "
                         "her at Google in healthcare advertising -- matches roster company exactly.",
        "urls": [
            "https://digipharma.wbresearch.com/speakers/stefani-klaskow",
            "https://hitlabsummit.sched.com/speaker/stefani_klaskow.1ummu38l",
        ],
    },
    "Travis Kupp": {
        "verification": "His own community-platform bio page names 'UCB, a global biopharmaceutical "
                         "company' and 'Head of Futures' -- matches roster company/designation exactly.",
        "urls": [
            "https://www.futures4europe.eu/person/travis-kupp-plriq",
        ],
    },
    "Yukti Khurana": {
        "verification": "Company org-chart page (theorg.com) names her 'Director, Medical Insights & "
                         "Impact at Astellas Pharma' -- an exact match to roster designation/company.",
        "urls": [
            "https://theorg.com/org/astellas-pharma/person/yukti-khurana",
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
