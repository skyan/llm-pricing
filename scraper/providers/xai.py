"""xAI pricing scraper. JS-rendered docs page, needs Playwright."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing, PlaywrightMixin


class XaiScraper(PlaywrightMixin, BaseScraper):
    provider_id = "xai"
    provider_name = "xAI"
    website = "https://x.ai"
    pricing_url = "https://docs.x.ai/developers/models"
    currency = "USD"
    playwright_wait_selector = "table"
    playwright_post_wait_ms = 1500

    def fetch_html(self) -> str:
        html = BaseScraper.fetch_html(self)
        if self._looks_rendered(html):
            return html
        return PlaywrightMixin.fetch_html(self)

    def parse_soup(self, soup: BeautifulSoup) -> list:
        embedded_models = self._parse_embedded_models(str(soup))
        if embedded_models:
            return embedded_models

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

                if display == "Grok 4":
                    continue

                # Skip duplicates
                if any(m.name == mid for m in models):
                    continue

                models.append(ModelPricing(
                    name=mid,
                    display_name=display,
                    context_window=ctx if ctx > 0 else 131072,
                    input_price=inp,
                    output_price=out,
                    tier=self._detect_tier(name, display),
                ))

        return models

    @staticmethod
    def _looks_rendered(html: str) -> bool:
        text = html.lower()
        return "grok" in text and "$" in text and ("<table" in text or "model pricing" in text)

    def _parse_embedded_models(self, html: str) -> list:
        pattern = re.compile(
            r'\\"name\\":\\"(grok-[^\\"]+)\\".*?'
            r'\\"promptTextTokenPrice\\":\\"\$n(\d+)\\".*?'
            r'\\"cachedPromptTokenPrice\\":\\"\$n(\d+)\\".*?'
            r'\\"completionTextTokenPrice\\":\\"\$n(\d+)\\".*?'
            r'\\"maxPromptLength\\":(\d+)',
            re.S,
        )

        best_by_key = {}
        for match in pattern.finditer(html):
            raw_name = match.group(1)
            if not raw_name.startswith("grok-4"):
                continue
            if any(skip in raw_name for skip in ("imagine", "code")):
                continue

            input_price = self._cents_per_100m_to_usd_per_1m(match.group(2))
            cached_price = self._cents_per_100m_to_usd_per_1m(match.group(3))
            output_price = self._cents_per_100m_to_usd_per_1m(match.group(4))
            context_window = int(match.group(5))
            base_key = raw_name.replace("-non-reasoning", "").replace("-reasoning", "")

            candidate = ModelPricing(
                name=raw_name,
                display_name=self._clean_name(raw_name),
                context_window=context_window,
                input_price=input_price,
                cached_input_price=cached_price,
                output_price=output_price,
                tier=self._detect_tier(raw_name, self._clean_name(raw_name)),
            )

            if candidate.display_name == "Grok 4":
                continue

            existing = best_by_key.get(base_key)
            if existing is None:
                best_by_key[base_key] = candidate
                continue

            # Prefer reasoning variants when pricing is identical.
            if "reasoning" in raw_name and "non-reasoning" not in raw_name:
                best_by_key[base_key] = candidate

        return list(best_by_key.values())

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
        name = re.sub(r'-(\d{4,})(?=-|$)', '', name)  # Remove date-like suffix anywhere
        name = name.replace("-non-reasoning", "-reasoning")
        name = name.replace("grok-4-1", "grok-4.1")
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

    @staticmethod
    def _cents_per_100m_to_usd_per_1m(value: str) -> float:
        return round(int(value) / 10000, 4)

    @staticmethod
    def _detect_tier(raw_name: str, display_name: str) -> str | None:
        lowered = raw_name.lower()
        if any(token in lowered for token in ("fast", "mini")):
            return "lite"
        if re.fullmatch(r'grok-\d+(?:\.\d+)?(?:-\d{4,})?', lowered):
            return "pro"
        if re.fullmatch(r'Grok \d+(?:\.\d+)?', display_name):
            return "pro"
        return None
