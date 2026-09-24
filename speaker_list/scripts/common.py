import glob
import json
import os
import re
import time
from difflib import SequenceMatcher

from deep_translator import MyMemoryTranslator
from dotenv import load_dotenv
from langdetect import DetectorFactory, LangDetectException, detect_langs

load_dotenv()

# Registering an email with MyMemory raises the free quota from 5k to 50k chars/day.
MYMEMORY_EMAIL = os.getenv("MYMEMORY_EMAIL")

INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')


def slugify_name(speaker_name):
    """Turn a speaker name into a filesystem-safe folder name (Windows-safe)."""
    cleaned = INVALID_CHARS.sub("", speaker_name).strip().rstrip(". ")
    return cleaned or "unknown-speaker"


def speaker_dir(name):
    return f"speaker_list/{slugify_name(name)}"


def bronze_speaker_names(bronze_filename="linkedin.json"):
    """Names of everyone with a bronze file on disk, regardless of whether
    they have a linkedin_url in the master roster. Covers speakers recovered
    via manual URL research (see Bronze-layer-LinkedIn-Recovery.py) who the
    master roster has no way to reference."""
    names = set()
    for path in glob.glob(f"speaker_list/*/data/bronze/{bronze_filename}"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("status") == "success":
            names.add(data["speaker_name"])
    return names


# Speakers deliberately excluded from LinkedIn enrichment. They remain in the
# master roster (speaker/data/gold/speakers.json) -- they really did speak at
# these events -- but neither source can return usable data for them, so
# re-running the bronze layers would only waste API credits.
#
# Paméla Graas and Lois-An Gregory were here after their first attempt (bot-block
# / empty PDL match), but a later retry succeeded with real content -- LinkedIn's
# bot-blocking is not permanent, so this list should be re-checked periodically
# rather than treated as final.
SKIP_SPEAKERS = set()


def is_skipped(speaker_name):
    return speaker_name in SKIP_SPEAKERS


# langdetect's ISO 639-1 code -> MyMemoryTranslator's region-qualified code
LANG_CODE_MAP = {
    "fr": "fr-FR", "de": "de-DE", "es": "es-ES", "it": "it-IT", "pt": "pt-PT",
    "nl": "nl-NL", "pl": "pl-PL", "ro": "ro-RO", "hr": "hr-HR", "sv": "sv-SE",
    "da": "da-DK", "fi": "fi-FI", "el": "el-GR", "tr": "tr-TR", "ru": "ru-RU",
    "ar": "ar-SA", "ja": "ja-JP", "ko": "ko-KR", "hi": "hi-IN", "cs": "cs-CZ",
    "hu": "hu-HU", "sk": "sk-SK", "sl": "sl-SI", "bg": "bg-BG", "uk": "uk-UA",
    "he": "he-IL", "id": "id-ID", "vi": "vi-VN", "th": "th-TH", "no": "nb-NO",
    "zh-cn": "zh-CN", "zh-tw": "zh-TW", "ca": "ca-ES",
}


# langdetect samples randomly and gives different answers on re-runs unless seeded.
DetectorFactory.seed = 0

# MyMemory rejects requests over 500 characters (NotValidLength); leave headroom.
MAX_CHUNK = 450


def _chunk_sentences(text):
    """Split on sentence boundaries into pieces that each fit MyMemory's limit."""
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    chunks, current = [], ""
    for s in sentences:
        if len(s) > MAX_CHUNK:  # a single runaway sentence: hard-split it
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(s[i:i + MAX_CHUNK] for i in range(0, len(s), MAX_CHUNK))
            continue
        if len(current) + len(s) + 1 > MAX_CHUNK:
            chunks.append(current)
            current = s
        else:
            current = f"{current} {s}".strip()
    if current:
        chunks.append(current)
    return chunks


# A "translation" this similar to its input was echoed back untouched -- the
# source language was wrong, or the text is a name/untranslatable fragment.
ECHO_THRESHOLD = 0.85


def _is_echo(source, result):
    return SequenceMatcher(None, source, result).ratio() >= ECHO_THRESHOLD


def _translate_with(source_code, text):
    translator = MyMemoryTranslator(source=source_code, target="en-GB", email=MYMEMORY_EMAIL)
    parts = []
    for chunk in _chunk_sentences(text):
        parts.append(translator.translate(chunk))
        time.sleep(0.3)  # stay well under MyMemory's per-second rate limit across thousands of calls
    return " ".join(parts)


def translate_to_english(text):
    """Best-effort translation to English. Returns None if the text is already
    English, is a bare name, can't be translated, or only echoes back unchanged
    -- never raises, since this must not break the pipeline on a bad string."""
    if not text or len(text.strip()) < 3:
        return None

    # langdetect is unreliable on short social snippets full of proper nouns, so
    # try its ranked candidates in turn rather than trusting only the top one.
    try:
        candidates = [c.lang for c in detect_langs(text)]
    except LangDetectException:
        return None

    if not candidates or candidates[0] == "en":
        return None

    for lang in candidates[:3]:
        source_code = LANG_CODE_MAP.get(lang)
        if not source_code:
            continue
        try:
            result = _translate_with(source_code, text)
        except Exception:
            continue
        if result and not _is_echo(text, result):
            return result

    return None
