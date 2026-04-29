"""Google Vertex AI pricing scraper. Static HTML with rowspan pattern."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class GoogleScraper(BaseScraper):
    provider_id = "google"
    provider_name = "Google"
    website = "https://ai.google.dev"
    pricing_url = "https://cloud.google.com/vertex-ai/generative-ai/pricing"
    currency = "USD"

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        tables = soup.find_all("table")

        for table in tables:
            # Check if this looks like a pricing table
            headers = []
            thead = table.find("thead")
            if thead:
                headers = [th.get_text(strip=True).lower() for th in thead.find_all("th")]

            # Detect relevant columns
            model_col = None
            input_col = None
            output_col = None
            cached_col = None

            for i, h in enumerate(headers):
                hl = h.lower()
                if "model" in hl:
                    model_col = i
                if "input" in hl and "cached" not in hl:
                    input_col = i
                if "output" in hl and "text" in hl:
                    output_col = i
                if "cached" in hl:
                    cached_col = i

            rows = table.find_all("tr")
            current_model = None

            for row in rows:
                cells = row.find_all(["td", "th"])
                if not cells:
                    continue

                # Check for rowspan model cell
                first_cell = cells[0]
                if first_cell.get("rowspan") or (first_cell.name == "th" and first_cell.get_text(strip=True)):
                    model_text = first_cell.get_text(strip=True)
                    if model_text and not any(h in model_text.lower() for h in ["model", "input", "output", "feature"]):
                        current_model = model_text

                if not current_model:
                    continue

                # Parse row for pricing
                row_text = " ".join(c.get_text(strip=True) for c in cells)

                # Only process rows that contain "input" or "output" for text
                if "gemini" in current_model.lower() or "palm" in current_model.lower():
                    pass  # process

                # Extract prices from cells
                prices_in_row = []
                for cell in cells:
                    text = cell.get_text(strip=True)
                    p = self._extract_usd(text)
                    if p is not None and p > 0:
                        prices_in_row.append(p)

                if len(prices_in_row) < 2:
                    continue

                # Figure out which columns from header mapping
                model_name = current_model.strip()
                # Skip non-model rows
                if len(model_name) > 60 or "$" in model_name:
                    continue

                # The rowspan pattern means we need to accumulate for each model
                self._add_or_update(models, model_name, prices_in_row)

        # Deduplicate and merge
        return self._merge_models(models)

    @staticmethod
    def _extract_usd(text: str):
        text = text.replace(",", "").replace(" ", "")
        m = re.search(r'\$(\d+\.?\d*)', text)
        if m:
            val = float(m.group(1))
            return val if val > 0 else None
        return None

    def _add_or_update(self, models: list, name: str, prices: list):
        ctx = 128000
        n = name.lower()
        if "2.5" in n or "2.0" in n:
            ctx = 1000000
        elif "1.5" in n:
            ctx = 128000

        display = name
        mid = re.sub(r'\s*\(.*?\)', '', name).strip().lower().replace(" ", "-")

        # For Google, smallest price is usually cached input, then input, then output
        sorted_prices = sorted(set(prices))
        input_price = sorted_prices[1] if len(sorted_prices) >= 2 else sorted_prices[0]
        cached_price = sorted_prices[0] if len(sorted_prices) >= 2 else None
        output_price = sorted_prices[-1]

        models.append(ModelPricing(
            name=mid,
            display_name=display,
            context_window=ctx,
            input_price=input_price,
            cached_input_price=cached_price,
            output_price=output_price,
        ))

    @staticmethod
    def _merge_models(models: list) -> list:
        """Merge duplicate model entries keeping the one with most data."""
        seen = {}
        for m in models:
            if m.name in seen:
                existing = seen[m.name]
                if m.input_price and not existing.input_price:
                    existing.input_price = m.input_price
                if m.output_price and not existing.output_price:
                    existing.output_price = m.output_price
                if m.cached_input_price and not existing.cached_input_price:
                    existing.cached_input_price = m.cached_input_price
            else:
                seen[m.name] = m
        return list(seen.values())
