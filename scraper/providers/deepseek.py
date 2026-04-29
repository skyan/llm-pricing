"""DeepSeek pricing scraper. Static Docusaurus page with a feature/pricing table."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class DeepseekScraper(BaseScraper):
    provider_id = "deepseek"
    provider_name = "DeepSeek"
    website = "https://api-docs.deepseek.com"
    pricing_url = "https://api-docs.deepseek.com/quick_start/pricing"
    currency = "USD"

    def parse_soup(self, soup: BeautifulSoup) -> list:
        article = soup.find("article") or soup.find(class_="markdown")
        if not article:
            return []
        tables = article.find_all("table")
        if not tables:
            return []

        table = tables[0]
        rows = table.find_all("tr")
        if len(rows) < 2:
            return []

        # Header row: first cell is "MODEL", rest are model names
        header_cells = rows[0].find_all(["td", "th"])
        model_names = []
        for cell in header_cells[1:]:
            text = re.sub(r'\(.*?\)', '', cell.get_text(strip=True)).strip()
            if text:
                model_names.append(text)

        if not model_names:
            return []

        # Parse data rows
        prices = {}
        context_windows = {}
        ctx_for_all = 0

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            label0 = cells[0].get_text(strip=True).lower()

            # Rows with section header in first cell (e.g. "PRICING", "FEATURES")
            if label0 in ("pricing", "features", "model version"):
                sub_label = cells[1].get_text(strip=True).lower() if len(cells) > 1 else ""
                self._parse_sub_row(sub_label, cells[2:], model_names, prices, context_windows)
                continue

            label = label0
            label_clean = re.sub(r'\(.*?\)', '', label).strip()

            # Context length row
            if "context" in label_clean:
                ctx = self.extract_context(cells[1].get_text(strip=True)) if len(cells) > 1 else 0
                if ctx:
                    ctx_for_all = ctx
                continue

            # Max output row
            if "max output" in label_clean:
                continue

            # Single-value rows (same for all models)
            if len(cells) == 2:
                continue

            # Multi-column pricing/feature rows
            for i, cell in enumerate(cells[1:]):
                if i >= len(model_names):
                    break
                mname = model_names[i]
                text = cell.get_text(strip=True)

                if "cache hit" in label:
                    prices.setdefault(mname, {})["cache_hit"] = self.extract_price(text)
                elif "cache miss" in label:
                    prices.setdefault(mname, {})["cache_miss"] = self.extract_price(text)
                elif "input" in label_clean and "cache" not in label:
                    prices.setdefault(mname, {})["input"] = self.extract_price(text)
                elif "output" in label_clean and "max" not in label_clean:
                    prices.setdefault(mname, {})["output"] = self.extract_price(text)

        # Build model list
        models = []
        for mname in model_names:
            if not mname:
                continue
            p = prices.get(mname, {})
            ctx = context_windows.get(mname, ctx_for_all)
            models.append(ModelPricing(
                name=mname.lower().replace(" ", "-"),
                display_name=self._pretty_name(mname),
                context_window=ctx,
                input_price=p.get("input", p.get("cache_miss", 0)),
                cached_input_price=p.get("cache_hit"),
                output_price=p.get("output", 0),
            ))

        return models

    def _parse_sub_row(self, label: str, cells, model_names, prices, context_windows):
        """Parse a row where first cell was a section header."""
        for i, cell in enumerate(cells):
            if i >= len(model_names):
                break
            mname = model_names[i]
            text = cell.get_text(strip=True)
            if "cache hit" in label:
                prices.setdefault(mname, {})["cache_hit"] = self.extract_price(text)
            elif "cache miss" in label:
                prices.setdefault(mname, {})["cache_miss"] = self.extract_price(text)
            elif "input" in label:
                prices.setdefault(mname, {})["input"] = self.extract_price(text)
            elif "output" in label:
                prices.setdefault(mname, {})["output"] = self.extract_price(text)

    @staticmethod
    def _pretty_name(name: str) -> str:
        name = name.strip()
        if not name:
            return name
        parts = name.split("-")
        if parts[0].lower() == "deepseek":
            parts[0] = "DeepSeek"
        return " ".join(p.capitalize() if p.lower() not in ("v4",) else p.upper() for p in parts)
