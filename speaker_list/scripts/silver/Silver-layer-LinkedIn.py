import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scripts.common import bronze_speaker_names, is_skipped, speaker_dir, translate_to_english  # noqa: E402

GOLD_SPEAKERS_PATH = "speaker/data/gold/speakers.json"

SECTION_HEADERS = [
    "About", "Experience", "Education", "Publications", "Honors & Awards",
    "Certifications", "Volunteering", "Languages", "Organizations", "Activity",
    "People Also Viewed",
]

REDACTED_RE = re.compile(r"^[\*\-\s]+$")


def split_sections(markdown):
    """Split raw LinkedIn markdown into a dict of {section_name: body_text}."""
    if not markdown:
        return {}

    pattern = r"^##\s+(" + "|".join(re.escape(h) for h in SECTION_HEADERS) + r")\s*$"
    parts = re.split(pattern, markdown, flags=re.MULTILINE)

    sections = {}
    # parts[0] is the header block (name/company/location) before the first "## " section
    for i in range(1, len(parts), 2):
        name = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        sections[name] = body
    return sections, parts[0].strip() if parts else ""


def parse_header(header_text):
    """Header block looks like:
    # Dana Vigier, MD
    **Alexion Pharmaceuticals, Inc.**
    France, FR
    500 connections, 2962 followers
    """
    full_name = None
    current_company = None
    location = None
    connections = None
    followers = None

    name_match = re.search(r"^#\s+(.+)$", header_text, flags=re.MULTILINE)
    if name_match:
        full_name = name_match.group(1).strip()

    company_match = re.search(r"^\*\*(.+)\*\*$", header_text, flags=re.MULTILINE)
    if company_match:
        current_company = company_match.group(1).strip()

    conn_match = re.search(r"([\d,]+)\s+connections", header_text)
    if conn_match:
        connections = conn_match.group(1).replace(",", "")

    follow_match = re.search(r"([\d,]+)\s+followers", header_text)
    if follow_match:
        followers = follow_match.group(1).replace(",", "")

    lines = [l.strip() for l in header_text.splitlines() if l.strip()]
    for line in lines:
        if line.startswith("#") or line.startswith("**"):
            continue
        if "connections" in line or "followers" in line:
            continue
        location = line
        break

    return {
        "full_name": full_name,
        "current_company": current_company,
        "location": location,
        "connections": connections,
        "followers": followers,
    }


def parse_experience(body):
    """Experience entries are blocks of:
    ### Company Name
    [Company Name](link)
    Start - End
    Location
    """
    if not body or body.strip() == "N/A":
        return []

    entries = []
    blocks = re.split(r"^###\s+", body, flags=re.MULTILINE)[1:]
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        title = lines[0]
        duration = None
        for line in lines[1:]:
            if re.search(r"\d{4}|Present", line) and "[" not in line:
                duration = line
                break
        redacted = bool(REDACTED_RE.match(title))
        entries.append({"title": title, "duration": duration, "redacted": redacted})
    return entries


def parse_education(body):
    """Same markdown-block shape as Experience:
    ### School Name
    [School Name](N/A)
    start - end
    N/A
    """
    if not body or body.strip() == "N/A":
        return []

    entries = []
    blocks = re.split(r"^###\s+", body, flags=re.MULTILINE)[1:]
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        school = lines[0]
        duration = None
        for line in lines[1:]:
            if re.search(r"\d{4}|Present", line) and "[" not in line:
                duration = line
                break
        if REDACTED_RE.match(school) or school == "N/A":
            continue  # nothing usable in this entry
        entries.append({"school": school, "duration": duration})
    return entries


def parse_activity(body):
    """Activity entries look like:
    - **post text preview…**
    Liked by X
    [View Post](url)
    ![Activity Image](img_url)
    """
    if not body or body.strip() == "N/A":
        return []

    chunks = re.split(r"\n(?=- \*\*)", body.strip())
    posts = []
    for chunk in chunks:
        text_match = re.match(r"-\s+\*\*(.+?)\*\*", chunk, flags=re.DOTALL)
        if not text_match:
            continue
        interaction_match = re.search(r"^(Liked by|Shared by|Commented on|Reposted|Celebrates).*$", chunk, flags=re.MULTILINE)
        url_match = re.search(r"\[View Post\]\((.+?)\)", chunk)
        image_match = re.search(r"!\[Activity Image\]\((.+?)\)", chunk)

        post_text = text_match.group(1).strip()
        posts.append({
            "text": post_text,
            "text_en": translate_to_english(post_text),
            "interaction": interaction_match.group(0).strip() if interaction_match else None,
            "post_url": url_match.group(1) if url_match else None,
            "image_url": image_match.group(1) if image_match else None,
        })
    return posts


def parse_people_also_viewed(body):
    """Lines look like: - Name (Company) - https://linkedin.com/in/..."""
    if not body or body.strip() == "N/A":
        return []

    people = []
    for line in body.strip().splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        match = re.match(r"-\s+(.+?)\s+\((.+?)\)\s+-\s+(\S+)", line)
        if match:
            people.append({
                "name": match.group(1).strip(),
                "company": None if match.group(2).strip() in ("None", "N/A") else match.group(2).strip(),
                "profile_url": match.group(3).strip(),
            })
    return people


def clean_na(value):
    if value is None:
        return None
    value = value.strip()
    return None if value in ("", "N/A") else value


def main():
    with open(GOLD_SPEAKERS_PATH, encoding="utf-8") as f:
        gold_speakers = json.load(f)

    speaker_names = {s["speaker_name"] for s in gold_speakers
                     if s.get("linkedin_url") and not is_skipped(s["speaker_name"])}
    speaker_names |= {n for n in bronze_speaker_names() if not is_skipped(n)}

    processed = 0
    skipped = 0

    for name in sorted(speaker_names):
        bronze_path = f"{speaker_dir(name)}/data/bronze/linkedin.json"
        if not os.path.exists(bronze_path):
            continue

        with open(bronze_path, encoding="utf-8") as f:
            bronze = json.load(f)

        if bronze.get("status") != "success":
            skipped += 1
            continue

        sections, header_text = split_sections(bronze.get("raw_content", ""))
        header = parse_header(header_text)

        silver = {
            "record_id": bronze["record_id"],
            "speaker_name": bronze["speaker_name"],
            "linkedin_url": bronze["linkedin_url"],
            "full_name": header["full_name"],
            "headline_company": header["current_company"],
            "location": header["location"],
            "connections": header["connections"],
            "followers": header["followers"],
            "about": clean_na(sections.get("About")),
            "about_en": translate_to_english(clean_na(sections.get("About"))),
            "experience": parse_experience(sections.get("Experience", "")),
            "education": parse_education(sections.get("Education", "")),
            "languages": clean_na(sections.get("Languages")),
            "languages_en": translate_to_english(clean_na(sections.get("Languages"))),
            "certifications": clean_na(sections.get("Certifications")),
            "certifications_en": translate_to_english(clean_na(sections.get("Certifications"))),
            "honors_and_awards": clean_na(sections.get("Honors & Awards")),
            "honors_and_awards_en": translate_to_english(clean_na(sections.get("Honors & Awards"))),
            "activity": parse_activity(sections.get("Activity", "")),
            "people_also_viewed": parse_people_also_viewed(sections.get("People Also Viewed", "")),
        }

        out_dir = f"{speaker_dir(name)}/data/silver"
        os.makedirs(out_dir, exist_ok=True)
        with open(f"{out_dir}/linkedin.json", "w", encoding="utf-8") as f:
            json.dump(silver, f, indent=2, ensure_ascii=False)

        processed += 1
        print(f"parsed: {name}")

    print(f"Done. {processed} silver records written, {skipped} bronze records skipped (not success)")


if __name__ == "__main__":
    main()
