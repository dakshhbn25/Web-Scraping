"""Build the agenda speakers list: people who speak in the agenda sessions but are NOT in the speakers list.

Reads   agenda/data/gold/sessions.json                 who speaks in which session
        speaker/data/gold/speakers.json                the speakers list (the master)
        ai_landscape/data/silver/contact_overrides.json  LinkedIn links found by hand for agenda-only people
Writes  agenda_speaker_list/agenda_speakers.json       one record per agenda-only person (the input of the enrichment scripts)
        agenda_speaker_list/agenda_speaker_map.json    every agenda person mapped to the speakers list, or marked agenda-only

Rule: a person counts once. If the agenda name matches a speakers-list name (ignoring titles such as Dr and apostrophe
variants) they are NOT added here; they are only mapped, and their data stays in speaker_list/. Run from the repo root.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "agenda_speaker_list"


def nk(name):
    """Name key: lower case, no titles, no punctuation, so 'Dr Kishan Rees' and 'Kishan Rees' are the same person."""
    t = re.sub(r"\b(dr|prof|mr|mrs|ms)\b\.?", " ", (name or "").lower())
    return re.sub(r"[^a-z0-9]+", "", t)


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


sessions = load(ROOT / "agenda/data/gold/sessions.json")
speakers = load(ROOT / "speaker/data/gold/speakers.json")
overrides = load(ROOT / "ai_landscape/data/silver/contact_overrides.json")["contacts"]
ov_by_key = {nk(k): (k, v) for k, v in overrides.items()}

by_key = defaultdict(list)
for r in speakers:
    by_key[nk(r["speaker_name"])].append(r)

people = {}
for s in sessions:
    for p in s["speakers"]:
        k = nk(p["speaker_name"])
        e = people.setdefault(k, {"name": p["speaker_name"], "designation": p["designation"], "company": p.get("company"), "events": [], "sessions": []})
        if s["event_name"] not in e["events"]:
            e["events"].append(s["event_name"])
        e["sessions"].append({"record_id": s["record_id"], "title": s["session_title"], "event_name": s["event_name"], "day": s["day"],
                              "start_time": s["start_time"], "track": s["track"], "source_urls": s.get("source_urls")})
        if not e["company"] and p.get("company"):
            e["company"] = p["company"]

mapping, new_people = {}, []
counter = defaultdict(int)
for k in sorted(people, key=lambda x: (people[x]["events"][0], people[x]["name"])):
    e = people[k]
    if k in by_key:
        recs = by_key[k]
        mapping[e["name"]] = {"status": "in speakers list", "matched_by": "exact name" if any(r["speaker_name"] == e["name"] for r in recs) else "name variant",
                              "speakers_list_name": recs[0]["speaker_name"], "speaker_record_ids": [r["record_id"] for r in recs]}
        continue
    ev = e["events"][0]
    rid = f"agenda-speaker-{ev.lower()}-{counter[ev]:03d}"
    counter[ev] += 1
    ov = ov_by_key.get(k)
    rec = {
        "record_id": rid, "speaker_name": e["name"], "designation": e["designation"], "company": e["company"],
        "event_name": ev, "events": e["events"], "event_year": 2026,
        "linkedin_url": ov[1]["linkedin_url"] if ov else None,
        "linkedin_url_source": "found by search and checked by hand" if ov else None,
        "linkedin_url_confidence": ov[1].get("confidence") if ov else None,
        "agenda_sessions": e["sessions"],
        "source_urls": sorted({u for s in e["sessions"] for u in (s.get("source_urls") or [])}),
        "in_speakers_list": False,
    }
    new_people.append(rec)
    mapping[e["name"]] = {"status": "agenda only", "agenda_speaker_record_id": rid}

OUT_DIR.mkdir(exist_ok=True)
(OUT_DIR / "agenda_speakers.json").write_text(json.dumps(new_people, indent=2, ensure_ascii=False), encoding="utf-8")
(OUT_DIR / "agenda_speaker_map.json").write_text(json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8")

in_list = [n for n, m in mapping.items() if m["status"] == "in speakers list"]
print(f"{len(people)} unique people in the agendas")
print(f"  already in the speakers list (mapped, not added): {len(in_list)}")
print(f"  agenda only (added to agenda_speakers.json): {len(new_people)}  | with a LinkedIn link: {sum(1 for r in new_people if r['linkedin_url'])}, without: {sum(1 for r in new_people if not r['linkedin_url'])}")
