"""OpenAI pricing scraper. JS-rendered SPA, requires Playwright."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing, PlaywrightMixin


class OpenAIScraper(PlaywrightMixin, BaseScraper):
    provider_id = "openai"
    provider_name = "OpenAI"
    website = "https://platform.openai.com"
    pricing_url = "https://platform.openai.com/docs/pricing"
    currency = "USD"

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        # Find all pricing tables - they have bordered rows with model data
        tables = soup.find_all("table")
        for table in tables:
            headers = []
            thead = table.find("thead")
            if thead:
                headers = [th.get_text(strip=True).lower() for th in thead.find_all("th")]
            else:
                first_row = table.find("tr")
                if first_row:
                    headers = [th.get_text(strip=True).lower() for th in first_row.find_all("th")]

            # Map column indices
            model_idx = self._find_col(headers, ["model", "name"])
            input_idx = self._find_col(headers, ["input"])
            output_idx = self._find_col(headers, ["output"])
            cached_idx = self._find_col(headers, ["cached", "cache", "prompt caching"])

            tbody = table.find("tbody") or table
            for row in tbody.find_all("tr"):
                cells = row.find_all("td")
                if not cells or len(cells) < 2:
                    cells = row.find_all("th")
                if len(cells) < 2:
                    continue

                name = self._clean_name(cells[model_idx].get_text(strip=True)) if model_idx is not None else ""
                if not name or name.lower() in ("model", "name", ""):
                    continue
                if "gpt" not in name.lower() and "o1" not in name.lower() and "o3" not in name.lower() and "o4" not in name.lower():
                    continue

                input_price = 0.0
                output_price = 0.0
                cached_price = None

                if input_idx is not None and input_idx < len(cells):
                    input_price = self._extract_usd(cells[input_idx].get_text(strip=True))
                if output_idx is not None and output_idx < len(cells):
                    output_price = self._extract_usd(cells[output_idx].get_text(strip=True))
                if cached_idx is not None and cached_idx < len(cells):
                    cached_price = self._extract_usd(cells[cached_idx].get_text(strip=True))
                    cached_price = cached_price if cached_price > 0 else None

                if input_price == 0 and output_price == 0:
                    continue

                models.append(ModelPricing(
                    name=name.lower().replace(" ", "-"),
                    display_name=self._normalize_display(name),
                    context_window=self._guess_context(name),
                    input_price=input_price,
                    cached_input_price=cached_price,
                    output_price=output_price,
                ))

        return models

    @staticmethod
    def _find_col(headers: list, keywords: list) -> int | None:
        for kw in keywords:
            for i, h in enumerate(headers):
                if kw in h:
                    return i
        return None

    @staticmethod
    def _clean_name(text: str) -> str:
        text = re.sub(r'\$[\d.]+.*$', '', text).strip()
        text = re.sub(r'/.*$', '', text).strip()
        return text

    @staticmethod
    def _extract_usd(text: str) -> float:
        text = text.replace(",", "").replace(" ", "")
        m = re.search(r'\$?(\d+\.?\d*)', text)
        if m:
            return float(m.group(1))
        return 0.0

    @staticmethod
    def _normalize_display(name: str) -> str:
        name = name.strip()
        if name and not name[0].isupper():
            name = name[0].upper() + name[1:] if len(name) > 1 else name.upper()
        return name

    @staticmethod
    def _guess_context(name: str) -> int:
        n = name.lower()
        if "128k" in n or "128" in n:
            return 128000
        if "200k" in n:
            return 200000
        if "1m" in n:
            return 1000000
        # Defaults for known models
        if "o1" in n or "o3" in n:
            return 200000
        return 128000
