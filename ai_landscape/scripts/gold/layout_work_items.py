"""Gold layer for the AI landscape map: embed each AI work item and project it to 2D.

Reads  ai_landscape/data/silver/work_items.json  (curated items for all 144 companies, each with a concept tag and relevance tier)
Writes ai_landscape/data/gold/ai_landscape.parquet  (one row per item, with x/y positions)

Run once, offline, whenever the work items change. It needs two packages the deployed app does
NOT use, so they are not in requirements.txt:  pip install fastembed umap-learn pandas pyarrow
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import umap
from fastembed import TextEmbedding

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "ai_landscape" / "data" / "silver" / "work_items.json"
OUT = ROOT / "ai_landscape" / "data" / "gold" / "ai_landscape.parquet"
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
K = 5
SEED = 42

items = json.loads(SRC.read_text(encoding="utf-8"))


def embed_text(t):
    # drop the boilerplate that marks the signal type, so the vector reflects the AI topic, not the phrasing
    return re.sub(r"^Agenda session:\s*", "", t)


texts = [embed_text(i["text"]) for i in items]
emb = np.array(list(TextEmbedding(MODEL).embed(texts)), dtype="float32")
emb /= np.linalg.norm(emb, axis=1, keepdims=True)

# tag check: does each item's text sit nearest to items of a different concept?
sim = emb @ emb.T
np.fill_diagonal(sim, -1)
codes = np.array([i["concept_code"] for i in items])
agree, other_top = [], []
for r in range(len(items)):
    nn = np.argsort(-sim[r])[: K + 3]
    nn = [n for n in nn if texts[n] != texts[r]][:K] or list(np.argsort(-sim[r])[:K])
    agree.append(float(np.mean(codes[nn] == codes[r])))
    others = Counter(c for c in codes[nn] if c != codes[r])
    other_top.append(max(others.values()) / len(nn) if others else 0.0)
agree, other_top = np.array(agree), np.array(other_top)
shares = Counter(codes)
chance = sum((v / len(codes)) ** 2 for v in shares.values())
print(f"tag agreement with text neighbours: {agree.mean():.2f} (chance about {chance:.2f})")

# semi-supervised UMAP: the concept tag gently pulls same-concept items together
y = np.array([ord(c) - ord("A") for c in codes])
xy = umap.UMAP(n_neighbors=10, min_dist=0.25, metric="cosine", random_state=SEED,
               target_metric="categorical", target_weight=0.45).fit_transform(emb, y=y)

# identical texts (one session, several companies) would overlap exactly: fan them out slightly
rng = np.random.default_rng(SEED)
span = float(max(np.ptp(xy[:, 0]), np.ptp(xy[:, 1])))
groups = defaultdict(list)
for idx, t in enumerate(texts):
    groups[t].append(idx)
for idxs in groups.values():
    if len(idxs) > 1:
        for k, idx in enumerate(idxs):
            ang = 2 * np.pi * k / len(idxs)
            xy[idx] += 0.012 * span * np.array([np.cos(ang), np.sin(ang)])
xy += rng.normal(0, 0.002 * span, xy.shape)

rows = []
for n, it in enumerate(items):
    gold = [f"{g['file']}:{g['record_id']}" for g in it["gold_records"]]
    rows.append({
        "id": it["id"], "company": it["company"], "company_type": it["company_type"], "relevance": it["relevance"], "text": it["text"],
        "concept": it["concept"], "concept_secondary": it["concept_secondary"] or "-", "team_served": it["team_served"],
        "decision_intelligence_fit": "n/a" if it["decision_intelligence_fit"] is None else ("Yes" if it["decision_intelligence_fit"] else "No"), "signal": it["signal"],
        "evidence_quality": it["evidence_quality"], "data_flag": it.get("data_flag", "none"), "date": it["date"],
        "source_url": it["source_urls"][0] if it["source_urls"] else "",
        "all_sources": " | ".join(it["source_urls"]), "gold_records": " | ".join(gold) if gold else "-",
        "tag_check": "n/a" if it["concept_code"] == "J" else ("review" if (agree[n] == 0 and other_top[n] >= 0.6) else "ok"),
        "x": float(xy[n, 0]), "y": float(xy[n, 1]),
    })
OUT.parent.mkdir(parents=True, exist_ok=True)
df = pd.DataFrame(rows)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sales_cards  # noqa: E402  (card fields: gold records written out, account signals, Phamax customer comparison)
df = sales_cards.build(df, items)
df.to_parquet(OUT, index=False)
print(f"wrote {len(df)} rows to {OUT}; {int((df.tag_check == 'review').sum())} flagged for review")
