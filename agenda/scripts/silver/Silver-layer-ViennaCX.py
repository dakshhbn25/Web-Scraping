import json
import re
import os
from bs4 import BeautifulSoup

BRONZE_PATH = "agenda/data/bronze/viennacx_agenda.json"
SILVER_PATH = "agenda/data/silver/viennacx_agenda.json"
EVENT_NAME = "ViennaCX"

TRACKS_TO_KEEP = {"MAIN STAGE", "AI STAGE"}


def load_bronze(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_text(value):
    if not value:
        return value
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def split_designation_company(text):
    text = normalize_text(text)
    if not text:
        return None, None
    if " at " in text:
        designation, company = text.rsplit(" at ", 1)
        return normalize_text(designation), normalize_text(company)
    return text, None


def extract_track(card):
    span = card.find("span")
    return normalize_text(span.get_text()) if span else None


def extract_times(card):
    time_p = card.find("p")
    time_text = normalize_text(time_p.get_text()) if time_p else None
    if not time_text:
        return None, None
    # normalize "03.30 PM" -> "03:30 PM" (a colon typo'd as a period on some cards)
    time_text = re.sub(r"(?<=\d)\.(?=\d)", ":", time_text)
    parts = re.split(r"\s*-\s*", time_text, maxsplit=1)
    if len(parts) == 2:
        return normalize_text(parts[0]), normalize_text(parts[1])
    return None, None


def extract_speakers(h3):
    content_div = h3.find_parent("div")
    speaker_container = content_div.find("div", class_=lambda c: c and "mt-8" in c)
    if not speaker_container:
        return []

    speakers = []
    for block in speaker_container.find_all("div", class_=lambda c: c and "flex" in c and "mt-4" in c):
        ps = block.find_all("p")
        if len(ps) < 2:
            continue
        name = normalize_text(ps[0].get_text())
        designation, company = split_designation_company(ps[1].get_text())
        speakers.append({
            "speaker_name": name,
            "designation": designation,
            "company": company,
        })
    return speakers


def parse_session_card(card, event_name, day_label, source_url, scraped_at):
    track = extract_track(card)
    if track not in TRACKS_TO_KEEP:
        return None

    h3 = card.find("h3")
    if not h3:
        return None

    start_time, end_time = extract_times(card)

    return {
        "session_title": normalize_text(h3.get_text()),
        "event_name": event_name,
        "day": day_label,
        "start_time": start_time,
        "end_time": end_time,
        "track": track,
        "speakers": extract_speakers(h3),
        "source_urls": [source_url],
        "scraped_at": scraped_at,
    }


def parse_sessions_from_html(html, event_name, source_url, scraped_at):
    soup = BeautifulSoup(html or "", "lxml")
    sessions = []

    for day_num in (1, 2):
        day_div = soup.find("div", id=f"day{day_num}")
        if not day_div:
            continue

        cards = day_div.find_all(
            "div",
            class_=lambda c: c and "border-t" in c and "border-neutral-200" in c and "py-8" in c,
        )
        for card in cards:
            session = parse_session_card(card, event_name, f"Day {day_num}", source_url, scraped_at)
            if session:
                sessions.append(session)

    return sessions


def main():
    bronze = load_bronze(BRONZE_PATH)
    source_url = bronze["metadata"].get("source_url")
    scraped_at = bronze.get("scraped_at")

    sessions = parse_sessions_from_html(bronze.get("html"), EVENT_NAME, source_url, scraped_at)

    total_speakers = sum(len(s["speakers"]) for s in sessions)
    print(f"{len(sessions)} sessions (Main Stage + AI Stage)")
    print(f"{total_speakers} speaker appearances across those sessions")

    os.makedirs("agenda/data/silver", exist_ok=True)
    with open(SILVER_PATH, "w", encoding="utf-8") as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(sessions)} sessions -> {SILVER_PATH}")


if __name__ == "__main__":
    main()