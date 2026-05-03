"""OpenAI pricing scraper. Uses developers.openai.com which is SSR and Playwright-friendly."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class OpenAIScraper(BaseScraper):
    provider_id = "openai"
    provider_name = "OpenAI"
    website = "https://platform.openai.com"
    pricing_url = "https://developers.openai.com/api/docs/pricing"
    currency = "USD"

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        tables = soup.find_all("table")
        if not tables:
            return models

        # Table 0 is the standard pay-as-you-go pricing
        table = tables[0]
        rows = table.find_all("tr")
        if len(rows) < 3:
            return models

        # Find header to detect columns
        headers = [c.get_text(strip=True).lower() for c in rows[1].find_all(["td", "th"])]
        # Expected: [Model, Input, Cached input, Output, Input(long), Cached(long), Output(long)]
        model_col = 0
        input_col = 1
        cached_col = 2
        output_col = 3

        for row in rows[2:]:  # Skip header rows
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                continue

            name = cells[model_col].get_text(strip=True) if model_col < len(cells) else ""
            if not name:
                continue

            # Only GPT-5.x series
            if not re.match(r'gpt-\d', name, re.IGNORECASE):
                continue

            display = self._format_name(name)

            # Short context pricing (columns 1-3)
            short_inp = self._parse_usd(cells[input_col].get_text(strip=True)) if input_col < len(cells) else 0
            short_cache = self._parse_usd(cells[cached_col].get_text(strip=True)) if cached_col < len(cells) else None
            short_out = self._parse_usd(cells[output_col].get_text(strip=True)) if output_col < len(cells) else 0

            # Long context pricing (columns 4-6)
            long_inp = self._parse_usd(cells[input_col + 3].get_text(strip=True)) if input_col + 3 < len(cells) else None
            long_cache = self._parse_usd(cells[cached_col + 3].get_text(strip=True)) if cached_col + 3 < len(cells) else None
            long_out = self._parse_usd(cells[output_col + 3].get_text(strip=True)) if output_col + 3 < len(cells) else None

            # Short context entry
            if short_inp or short_out:
                short_key = name.lower() + "-short"
                models.append(ModelPricing(
                    name=short_key,
                    display_name=display + " (≤256K)",
                    context_window=256000,
                    input_price=short_inp or 0,
                    cached_input_price=short_cache,
                    output_price=short_out or 0,
                ))

            # Long context entry
            if long_inp is not None or long_out is not None:
                long_key = name.lower() + "-long"
                models.append(ModelPricing(
                    name=long_key,
                    display_name=display + " (>256K)",
                    context_window=400000,
                    input_price=long_inp or 0,
                    cached_input_price=long_cache,
                    output_price=long_out or 0,
                ))

        return models

    @staticmethod
    def _parse_usd(text: str):
        text = text.replace(",", "").replace(" ", "").strip()
        if not text or text in ("-", ""):
            return None
        m = re.search(r'\$?(\d+\.?\d*)', text)
        if m:
            return float(m.group(1))
        return None

    @staticmethod
    def _format_name(name: str) -> str:
        name = name.replace("_", " ")
        parts = name.split("-")
        result = []
        for p in parts:
            pu = p.upper()
            if pu in ("GPT", "O1", "O3", "O4", "O5"):
                result.append(pu if pu.startswith("O") else pu)
            elif pu in ("PRO", "MINI", "NANO", "TURBO"):
                result.append(p.capitalize())
            elif p and p[0].isdigit():
                result.append(pu)
            else:
                result.append(p.capitalize())
        return " ".join(result)
