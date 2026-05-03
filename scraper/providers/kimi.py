"""Kimi (Moonshot) pricing scraper. Next.js SSR pages with custom table components."""

import re
import requests
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class KimiScraper(BaseScraper):
    provider_id = "kimi"
    provider_name = "Moonshot"
    website = "https://platform.kimi.com"
    pricing_url = "https://platform.kimi.com/docs/pricing"
    currency = "CNY"

    # Subpages: (slug, display_name, context_window)
    MODEL_PAGES = [
        ("chat-k26", "Kimi K2.6", 262144),
        ("chat-k25", "Kimi K2.5", 262144),
        ("chat-k2", "Kimi K2", 131072),
    ]

    def fetch_html(self) -> str:
        parts = []
        for slug, display, ctx in self.MODEL_PAGES:
            try:
                url = f"https://platform.kimi.com/docs/pricing/{slug}"
                resp = requests.get(url, timeout=30,
                                    headers={"User-Agent": "llm-pricing-bot/1.0"})
                resp.raise_for_status()
                meta = f"<!-- MODEL:{display}|{ctx} -->\n"
                parts.append(meta + resp.text)
            except Exception:
                continue
        return "\n".join(parts)

    def parse(self, html: str) -> list:
        models = []
        sections = html.split("<!-- MODEL:")
        for section in sections[1:]:
            try:
                meta_end = section.index("-->")
                meta = section[:meta_end].strip()
                display_name, ctx_str = meta.split("|")
                ctx = int(ctx_str)
            except (ValueError, IndexError):
                continue

            html_part = section[meta_end + 3:]

            # Kimi pages are Next.js SSR — prices are inline in the HTML
            # Look for ¥ price patterns near model context
            prices = re.findall(r'[¥￥]\s*(\d+\.?\d*)', html_part)
            prices = [float(p) for p in prices if float(p) > 0]

            if len(prices) < 3:
                continue

            # The K2 page has multiple models in a single table
            if display_name == "Kimi K2":
                models.extend(self._parse_k2_page(html_part, ctx))
                continue

            # Single model page: prices are [cache_hit, cache_miss, output]
            # Order in the HTML is usually: cache hit, cache miss, output
            models.append(ModelPricing(
                name=display_name.lower().replace(" ", "-"),
                display_name=display_name,
                context_window=ctx,
                input_price=round(prices[1], 2),     # cache miss = input price
                cached_input_price=round(prices[0], 2),  # cache hit
                output_price=round(prices[2], 2),
                tier="pro" if display_name in {"Kimi K2.6", "Kimi K2.5"} else None,
            ))

        return models

    def _parse_k2_page(self, html: str, ctx: int) -> list:
        """Parse K2 page which has multiple model variants in one table."""
        models = []
        soup = BeautifulSoup(html, "html.parser")

        # Try standard table
        table = soup.find("table")
        if not table:
            # Try doc-table wrapper
            wrap = soup.find(class_="doc-table-wrap")
            if wrap:
                table = wrap.find("table")

        if table:
            rows = table.find_all("tr")[1:]  # skip header
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 4:
                    continue
                name = cells[0].get_text(strip=True)
                if not name or len(name) > 60:
                    continue

                prices = []
                for cell in cells[1:]:
                    p = self.extract_price(cell.get_text(strip=True))
                    if p is not None:
                        prices.append(p)

                if len(prices) < 3:
                    continue

                display = self._clean_name(name)
                models.append(ModelPricing(
                    name=display.lower().replace(" ", "-"),
                    display_name=display,
                    context_window=ctx,
                    input_price=round(prices[1], 2),
                    cached_input_price=round(prices[0], 2),
                    output_price=round(prices[2], 2),
                    tier="pro" if display in {"Kimi K2.6", "Kimi K2.5"} else None,
                ))
            return models

        # Fallback: regex-based parsing for SSR content
        # Look for model name patterns followed by prices
        variants = re.findall(
            r'(kimi-k2[-_\w]*?)\s*[¥￥]\s*(\d+\.?\d*)\s*[¥￥]\s*(\d+\.?\d*)\s*[¥￥]\s*(\d+\.?\d*)',
            html, re.IGNORECASE
        )
        for variant in variants:
            name = self._clean_name(variant[0])
            models.append(ModelPricing(
                name=name.lower().replace(" ", "-"),
                display_name=name,
                context_window=ctx,
                input_price=round(float(variant[2]), 2),
                cached_input_price=round(float(variant[1]), 2),
                output_price=round(float(variant[3]), 2),
                tier="pro" if name in {"Kimi K2.6", "Kimi K2.5"} else None,
            ))

        return models

    @staticmethod
    def _clean_name(name: str) -> str:
        name = re.sub(r'\(.*?\)', '', name).strip()
        name = name.replace("kimi-", "Kimi ")
        parts = name.split("-")
        result = []
        for p in parts:
            if p.upper() in ("K2", "K2.6", "K2.5"):
                result.append(p.upper())
            elif p.lower() in ("turbo", "thinking", "preview"):
                result.append(p.capitalize())
            else:
                result.append(p.capitalize())
        return " ".join(result)

    def parse_soup(self, soup: BeautifulSoup) -> list:
        return []
