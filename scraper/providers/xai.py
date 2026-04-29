"""xAI pricing scraper. x.ai blocks scraping, use docs site and known pricing.

Since xAI actively blocks automated access to x.ai/pricing and doesn't publish
per-model token pricing on docs.x.ai, we use known pricing from public sources.
The docs site only has tool/storage pricing.
"""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class XaiScraper(BaseScraper):
    provider_id = "xai"
    provider_name = "xAI"
    website = "https://x.ai"
    pricing_url = "https://docs.x.ai/docs/models"
    currency = "USD"

    # Known pricing as of April 2026 (from public sources)
    KNOWN_PRICES = {
        "grok-4-1-fast": ("Grok 4.1 Fast", 2000000, 0.20, 0.05, 0.50),
        "grok-4-fast": ("Grok 4 Fast", 2000000, 0.20, 0.05, 0.50),
        "grok-4.20": ("Grok 4.20", 2000000, 2.00, 0.20, 6.00),
        "grok-4.20-multi-agent": ("Grok 4.20 Multi-Agent", 2000000, 2.00, 0.20, 6.00),
        "grok-code-fast-1": ("Grok Code Fast 1", 256000, 0.20, 0.02, 1.50),
        "grok-4": ("Grok 4", 256000, 3.00, 0.75, 15.00),
        "grok-3": ("Grok 3", 131072, 3.00, None, 15.00),
        "grok-3-mini": ("Grok 3 Mini", 131072, 0.30, None, 0.50),
    }

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        # Try to find any pricing tables on the docs page
        tables = soup.find_all("table")

        for table in tables:
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            if not any("price" in h or "cost" in h for h in headers):
                continue

            rows = table.find_all("tr")[1:]
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue
                name = cells[0].get_text(strip=True)
                if "grok" not in name.lower():
                    continue
                mid = name.lower().replace(" ", "-")
                display = name.strip()
                ctx = self.extract_context(cells[1].get_text(strip=True)) if len(cells) > 1 else 0
                inp = self.extract_price(cells[2].get_text(strip=True)) if len(cells) > 2 else 0
                cached = self.extract_price(cells[3].get_text(strip=True)) if len(cells) > 3 else None
                out = self.extract_price(cells[4].get_text(strip=True)) if len(cells) > 4 else 0
                models.append(ModelPricing(
                    name=mid, display_name=display, context_window=ctx,
                    input_price=inp or 0, cached_input_price=cached, output_price=out or 0,
                ))

        # If scraping failed, use known prices
        if not models:
            for mid, (display, ctx, inp, cached, out) in self.KNOWN_PRICES.items():
                models.append(ModelPricing(
                    name=mid, display_name=display, context_window=ctx,
                    input_price=inp, cached_input_price=cached, output_price=out,
                    notes="From public sources; official x.ai/pricing blocks scraping",
                ))

        return models
