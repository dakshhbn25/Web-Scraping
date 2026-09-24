import json
import re
import os
from urllib.parse import urlparse
from bs4 import BeautifulSoup

BRONZE_PATH = "speaker/data/bronze/dubrovnik.json"
SILVER_PATH = "speaker/data/silver/dubrovnik.json"
EVENT_NAME = "Dubrovnik"


def load_bronze(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_event_year(title):
    if not title:
        return None
    match = re.search(r"(20\d{2})", title)
    if match:
        return int(match.group(1))
    # fallback: standalone 2-digit token, e.g. "NEXT CX & AI 26 Pharma"
    match = re.search(r"(?<!\d)(\d{2})(?!\d)", title)
    if match:
        return 2000 + int(match.group(1))
    return None


def normalize_text(value):
    if not value:
        return value
    # collapse non-breaking spaces and other whitespace variants into regular spaces
    value = value.replace(" ", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def derive_domain_company(company_link):
    """Fall back to the company's own domain (e.g. 'gsk.com') as an unambiguous
    company identifier when the logo has no usable alt text. Never used for
    same-site placeholder links (nextpharmasummit.com/...)."""
    if not company_link:
        return None
    try:
        netloc = urlparse(company_link).netloc.lower()
    except ValueError:
        return None
    if netloc.startswith("www."):
        netloc = netloc[4:]
    if not netloc or "nextpharmasummit.com" in netloc:
        return None
    return netloc


def parse_speakers_from_html(html, event_name, event_year, source_url, scraped_at):
    soup = BeautifulSoup(html or "", "lxml")
    speakers = []
    seen = set()

    # each speaker's name/designation lives in a div like
    # <div class="mx-auto mt-4 max-w-[275px]"><h4>Name</h4><p>Designation</p></div>
    # and its photo/company-logo/linkedin-icon live in the sibling div right before it.
    text_divs = soup.find_all("div", class_=lambda c: c and "max-w-[275px]" in c and "mt-4" in c)

    for text_div in text_divs:
        h4 = text_div.find("h4")
        p = text_div.find("p")
        if not h4 or not p:
            continue
        name = normalize_text(h4.get_text())
        designation = normalize_text(p.get_text())
        if not name:
            continue

        key = name.lower()
        if key in seen:
            continue
        seen.add(key)

        photo_div = text_div.find_previous_sibling("div")
        company = None
        company_link = None
        company_source = None
        company_logo_filename = None
        linkedin_url = None
        if photo_div:
            linkedin_a = photo_div.find("a", class_="svg-linkedin", href=True)
            if linkedin_a and "linkedin.com/in/" in linkedin_a["href"]:
                linkedin_url = linkedin_a["href"]

            for a in photo_div.find_all("a", href=True):
                if a is linkedin_a:
                    continue
                company_link = a["href"]
                img = a.find("img")
                if img:
                    if img.get("alt"):
                        company = normalize_text(img["alt"]) or None
                        if company:
                            company_source = "alt_text"
                    if img.get("src"):
                        company_logo_filename = img["src"].split("/")[-1]
                break

            if not company:
                domain_company = derive_domain_company(company_link)
                if domain_company:
                    company = domain_company
                    company_source = "domain_inferred"

        speakers.append({
            "speaker_name": name,
            "designation": designation,
            "company": company,
            "company_link": company_link,
            "company_source": company_source,
            "company_logo_filename": company_logo_filename,
            "linkedin_url": linkedin_url,
            "event_name": event_name,
            "event_year": event_year,
            "source_urls": [source_url],
            "scraped_at": scraped_at,
        })

    return speakers


def main():
    bronze = load_bronze(BRONZE_PATH)

    event_year = extract_event_year(bronze["metadata"].get("title"))
    source_url = bronze["metadata"].get("source_url")
    scraped_at = bronze.get("scraped_at")

    speakers = parse_speakers_from_html(bronze.get("html"), EVENT_NAME, event_year, source_url, scraped_at)

    with_linkedin = sum(1 for s in speakers if s["linkedin_url"])
    with_company = sum(1 for s in speakers if s["company"])
    print(f"{with_linkedin} / {len(speakers)} speakers have a personal LinkedIn URL")
    print(f"{with_company} / {len(speakers)} speakers have a company")

    os.makedirs("speaker/data/silver", exist_ok=True)
    with open(SILVER_PATH, "w", encoding="utf-8") as f:
        json.dump(speakers, f, indent=2, ensure_ascii=False)

    print(f"Extracted {len(speakers)} speakers -> {SILVER_PATH}")


if __name__ == "__main__":
    main()
