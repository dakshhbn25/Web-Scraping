"""Re-attempt translation where it previously came back empty, or where the
stored "translation" merely echoed the source. Runs against silver files in
place; safe to re-run."""
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scripts.common import _is_echo, translate_to_english  # noqa: E402


def needs_retry(source, current):
    if not source:
        return False
    return not current or _is_echo(source, current)


# Top-level free-text fields that get a parallel *_en translation.
TRANSLATED_FIELDS = ("about", "languages", "certifications", "honors_and_awards")


def retry_field(container, key, stats):
    """Retry translation of container[key] into container[key + '_en']."""
    en_key = f"{key}_en"
    if not needs_retry(container.get(key), container.get(en_key)):
        return False
    stats["attempted"] += 1
    was_echo = bool(container.get(en_key))
    result = translate_to_english(container[key])
    if result:
        container[en_key] = result
        stats["recovered"] += 1
        return True
    if was_echo:
        container[en_key] = None  # drop the bogus echo rather than keep it
        stats["cleared"] += 1
        return True
    return False


def main():
    files = glob.glob("speaker_list/*/data/silver/linkedin.json")
    stats = {"attempted": 0, "recovered": 0, "cleared": 0}

    for path in files:
        with open(path, encoding="utf-8") as f:
            silver = json.load(f)
        changed = False

        for post in silver.get("activity") or []:
            changed |= retry_field(post, "text", stats)

        for field in TRANSLATED_FIELDS:
            changed |= retry_field(silver, field, stats)

        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(silver, f, indent=2, ensure_ascii=False)
            print(f"updated: {silver['speaker_name']}")

    print(f"Done. {stats['attempted']} fields re-checked, {stats['recovered']} translations recovered, "
          f"{stats['cleared']} bogus echoes cleared")


if __name__ == "__main__":
    main()
