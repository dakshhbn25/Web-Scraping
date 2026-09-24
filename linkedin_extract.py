from firecrawl import FirecrawlApp
from pydantic import BaseModel, Field
from typing import List, Optional

app = FirecrawlApp(api_key="fc-cf6936158991490da9c21a140fb9164c")


class Experience(BaseModel):
    title: str = Field(description="The job title")
    company: str = Field(description="Name of the employer company")
    duration: Optional[str] = Field(description="Timeframe or duration of the role")


class LinkedInProfileSchema(BaseModel):
    full_name: str = Field(description="The person's full name")
    headline: str = Field(description="The current profile headline or bio tagline")
    current_location: Optional[str] = Field(description="City and country of residence")
    experience_history: List[Experience] = Field(description="List of past and present jobs")


profile_url = "https://www.linkedin.com/in/dana-vigier-md-18ab0b7/"

try:
    # /v2/extract is deprecated (that's why it returned "no valid URLs" /
    # never actually crawled anything). Firecrawl's own response points to
    # /v2/scrape with a "json" format object instead.
    result = app.scrape(
        url=profile_url,
        formats=[
            {
                "type": "json",
                "prompt": "Extract the person's name, headline, location, and full professional work history.",
                "schema": LinkedInProfileSchema.model_json_schema(),
            }
        ],
    )

    print(result.json)

except Exception as e:
    print(f"Extraction failed: {e}")
