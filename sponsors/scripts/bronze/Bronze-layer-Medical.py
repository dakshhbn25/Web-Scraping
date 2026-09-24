from dotenv import load_dotenv
import os
import json
from datetime import datetime, timezone
from firecrawl import FirecrawlApp

load_dotenv()

app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))

result = app.scrape_url(
    "https://nextpharmasummit.com/Medical/sponsors/",
    formats=["markdown", "links", "html"],
)

data = result.model_dump()
data["scraped_at"] = datetime.now(timezone.utc).isoformat()

os.makedirs("sponsors/data/bronze", exist_ok=True)

with open("sponsors/data/bronze/medical.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Saved {len(data['markdown'])} characters and {len(data.get('links') or [])} links to sponsors/data/bronze/medical.json")