"""xAI pricing scraper. JS-rendered docs page, needs Playwright."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class XaiScraper(BaseScraper):
    provider_id = "xai"
    provider_name = "xAI"
    website = "https://x.ai"
    pricing_url = "https://docs.x.ai/docs/models"
    currency = "USD"

    def fetch_html(self) -> str:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.pricing_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            html = page.content()
            browser.close()
            return html

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        tables = soup.find_all("table")

        # Table 0 is the main model pricing table
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            header = [c.get_text(strip=True).lower() for c in rows[0].find_all(["td", "th"])]
            header_text = " ".join(header)

            # Only process token pricing tables (skip image/video pricing)
            if "input" not in header_text or "output" not in header_text:
                continue
            if "grok-imagine" in header_text.lower():
                continue

            # Find columns
            model_col = input_col = output_col = ctx_col = None
            for i, h in enumerate(header):
                if "model" in h:
                    model_col = i
                elif "input" in h:
                    input_col = i
                elif "output" in h:
                    output_col = i
                elif "context" in h:
                    ctx_col = i

            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < 3:
                    continue

                name = cells[model_col].get_text(strip=True) if model_col is not None and model_col < len(cells) else ""
                if not name or not name.lower().startswith("grok"):
                    continue
                if "imagine" in name.lower():
                    continue

                inp = self._extract_usd(cells[input_col].get_text(strip=True)) if input_col is not None and input_col < len(cells) else 0
                out = self._extract_usd(cells[output_col].get_text(strip=True)) if output_col is not None and output_col < len(cells) else 0
                ctx = self._parse_context(cells[ctx_col].get_text(strip=True)) if ctx_col is not None and ctx_col < len(cells) else 0

                if inp == 0:
                    continue

                # Clean model name, deduplicate reasoning/non-reasoning (same price)
                display = self._clean_name(name)
                mid = display.lower().replace(" ", "-")

                # Skip duplicates
                if any(m.name == mid for m in models):
                    continue

                models.append(ModelPricing(
                    name=mid,
                    display_name=display,
                    context_window=ctx if ctx > 0 else 131072,
                    input_price=inp,
                    output_price=out,
                ))

        return models

    @staticmethod
    def _extract_usd(text: str) -> float:
        m = re.search(r'\$(\d+\.?\d*)', text.replace(",", ""))
        return float(m.group(1)) if m else 0.0

    @staticmethod
    def _parse_context(text: str) -> int:
        text = text.upper().replace(" ", "").replace(",", "")
        if "M" in text:
            return int(float(text.replace("M", "")) * 1_000_000)
        if "K" in text:
            return int(float(text.replace("K", "")) * 1_000)
        m = re.search(r'(\d+)', text)
        return int(m.group(1)) if m else 0

    @staticmethod
    def _clean_name(name: str) -> str:
        name = re.sub(r'-\d{4,}$', '', name)  # Remove date suffix
        name = name.replace("-", " ").replace("_", " ")
        parts = name.split()
        result = []
        for p in parts:
            if p.lower() == "grok":
                result.append("Grok")
            elif p.lower() in ("fast", "mini", "reasoning", "non"):
                if p.lower() == "non":
                    continue
                result.append(p.capitalize())
            else:
                result.append(p.upper() if p.replace(".", "").isdigit() else p.capitalize())
        return " ".join(result)
