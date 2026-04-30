"""Anthropic pricing scraper. Direct fetch from platform.claude.com docs."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class AnthropicScraper(BaseScraper):
    provider_id = "anthropic"
    provider_name = "Anthropic"
    website = "https://www.anthropic.com"
    pricing_url = "https://platform.claude.com/docs/en/about-claude/pricing"
    currency = "USD"

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        tables = soup.find_all("table")
        if not tables:
            return models

        table = tables[0]
        rows = table.find_all("tr")
        if len(rows) < 2:
            return models

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 5:
                continue

            name = cells[0].get_text(strip=True)
            if not name or "deprecated" in name.lower():
                continue

            # Columns: Model | Base Input | 5m Cache Write | 1h Cache Write | Cache Hit | Output
            inp = self._extract_usd(cells[1].get_text(strip=True))
            cache_write = self._extract_usd(cells[2].get_text(strip=True))
            out = self._extract_usd(cells[5].get_text(strip=True))

            if inp == 0:
                continue

            models.append(ModelPricing(
                name=name.lower().replace(" ", "-"),
                display_name=name,
                context_window=200000,
                input_price=inp,
                cached_input_price=cache_write,
                output_price=out,
            ))

        return models

    @staticmethod
    def _extract_usd(text: str) -> float:
        m = re.search(r'\$(\d+\.?\d*)', text.replace(",", ""))
        return float(m.group(1)) if m else 0.0
