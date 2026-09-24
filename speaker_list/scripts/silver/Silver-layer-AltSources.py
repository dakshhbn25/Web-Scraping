"""Cleans the raw markdown scraped in Bronze-layer-AltSources.py. Unlike the
LinkedIn silver layer, these sources have no fixed template -- a podcast
page, a publisher's product page, and an alumni newsletter don't share a
structure -- so cleaning here just strips common boilerplate (nav link
lists, bare images) rather than parsing fields."""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scripts.common import speaker_dir  # noqa: E402

from importlib import import_module
_bronze_mod_path = os.path.join(os.path.dirname(__file__), "..", "bronze", "Bronze-layer-AltSources.py")
import importlib.util
_spec = importlib.util.spec_from_file_location("bronze_alt_sources", _bronze_mod_path)
bronze_alt_sources = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bronze_alt_sources)

# A line that's just a markdown link/image -- bare, bulleted, or wrapped in
# a heading -- is almost always nav/sidebar noise rather than body text.
_NAV_LINE_RE = re.compile(r"^\s*(?:#{1,6}\s*)?[*\-]?\s*!?\[.*?\]\(.*?\)\s*$")
_IMAGE_ONLY_RE = re.compile(r"^\s*!\[.*?\]\(.*?\)\s*$")


def clean_markdown(text):
    if not text:
        return ""
    lines = text.splitlines()
    kept = []
    for line in lines:
        if _NAV_LINE_RE.match(line) or _IMAGE_ONLY_RE.match(line):
            continue
        kept.append(line)
    # collapse 3+ blank lines down to 1
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept))
    return cleaned.strip()


def main():
    processed = 0
    for name in bronze_alt_sources.SOURCES:
        bronze_path = f"{speaker_dir(name)}/data/bronze/alt_sources.json"
        if not os.path.exists(bronze_path):
            continue
        with open(bronze_path, encoding="utf-8") as f:
            bronze = json.load(f)
        if bronze.get("status") != "success":
            continue

        silver = {
            "speaker_name": name,
            "verification": bronze["verification"],
            "sources": [],
        }
        for page in bronze["pages"]:
            if page["status"] != "success":
                continue
            cleaned = clean_markdown(page.get("raw_content"))
            silver["sources"].append({
                "url": page["url"],
                "title": page.get("title"),
                "text": cleaned,
            })

        out_dir = f"{speaker_dir(name)}/data/silver"
        os.makedirs(out_dir, exist_ok=True)
        with open(f"{out_dir}/alt_sources.json", "w", encoding="utf-8") as f:
            json.dump(silver, f, indent=2, ensure_ascii=False)
        processed += 1
        print(f"cleaned: {name} ({len(silver['sources'])} sources)")

    print(f"Done. {processed} silver alt-source records written")


if __name__ == "__main__":
    main()
