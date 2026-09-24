"""Surgical patch: re-parse only the 'education' field from bronze raw_content
into the already-written silver files, without re-running translation (which
would burn API quota re-doing work that's already correct).

One-off cleanup for silver files written before parse_education() existed in
Silver-layer-LinkedIn.py. Safe to delete once no silver file has a string
(rather than list) 'education' field.
"""
import glob
import importlib.util
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

_silver_mod_path = os.path.join(os.path.dirname(__file__), "Silver-layer-LinkedIn.py")
_spec = importlib.util.spec_from_file_location("silver_linkedin", _silver_mod_path)
silver_linkedin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(silver_linkedin)


def main():
    patched = 0
    for path in glob.glob("speaker_list/*/data/silver/linkedin.json"):
        with open(path, encoding="utf-8") as f:
            silver = json.load(f)

        if isinstance(silver.get("education"), list):
            continue  # already in the new shape

        bronze_path = path.replace("silver", "bronze")
        if not os.path.exists(bronze_path):
            continue
        with open(bronze_path, encoding="utf-8") as f:
            bronze = json.load(f)

        sections, _ = silver_linkedin.split_sections(bronze.get("raw_content", ""))
        silver["education"] = silver_linkedin.parse_education(sections.get("Education", ""))

        with open(path, "w", encoding="utf-8") as f:
            json.dump(silver, f, indent=2, ensure_ascii=False)
        patched += 1
        print(f"patched: {silver['speaker_name']}")

    print(f"Done. {patched} silver files patched")


if __name__ == "__main__":
    main()
