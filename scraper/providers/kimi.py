"""Kimi (Moonshot) pricing scraper. Card-based docs, multiple subpages."""

import re
import requests
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class KimiScraper(BaseScraper):
    provider_id = "kimi"
    provider_name = "Kimi"
    website = "https://kimi.moonshot.cn"
    pricing_url = "https://platform.kimi.com/docs/pricing"
    currency = "CNY"

    # Model subpages to scrape
    MODEL_PAGES = [
        ("chat-k26", "Kimi K2.6", 262144),
        ("chat-k2", "Kimi K2", 131072),
        ("chat-v1", "Kimi V1", 131072),
    ]

    def fetch_html(self) -> str:
        # For Kimi, the main page is a card index. We'll scrape subpages.
        # Return a combined HTML for parsing
        parts = []
        for slug, display, ctx in self.MODEL_PAGES:
            try:
                url = f"https://platform.kimi.com/docs/pricing/{slug}"
                resp = requests.get(url, timeout=30,
                                    headers={"User-Agent": "llm-pricing-bot/1.0"})
                resp.raise_for_status()
                # Embed model metadata in the HTML
                meta = f'<!-- MODEL:{display}|{ctx} -->\n'
                parts.append(meta + resp.text)
            except Exception:
                continue
        return "\n".join(parts)

    def parse(self, html: str) -> list:
        models = []
        # Split combined HTML by model markers
        sections = html.split("<!-- MODEL:")
        for section in sections[1:]:  # first is empty
            meta_end = section.index("-->")
            meta = section[:meta_end].strip()
            display_name, ctx_str = meta.split("|")
            ctx = int(ctx_str)

            soup = BeautifulSoup(section[meta_end + 3:], "html.parser")

            # Find pricing table - Kimi uses doc-table-wrap > doc-table
            table = soup.find("table")
            if not table:
                continue

            rows = table.find_all("tr")
            input_price = 0.0
            output_price = 0.0
            cached_price = None

            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                label = cells[0].get_text(strip=True).lower()
                value = cells[1].get_text(strip=True) if len(cells) > 1 else ""

                p = self.extract_price(value)
                if p is None:
                    continue

                if "输入" in label or "input" in label:
                    if "缓存" in label or "cache" in label:
                        cached_price = p
                    else:
                        input_price = p
                elif "输出" in label or "output" in label:
                    output_price = p

            if input_price == 0 and output_price == 0:
                continue

            mid = display_name.lower().replace(" ", "-")
            models.append(ModelPricing(
                name=mid, display_name=display_name, context_window=ctx,
                input_price=round(input_price, 2),
                cached_input_price=round(cached_price, 2) if cached_price else None,
                output_price=round(output_price, 2),
            ))

        return models

    def parse_soup(self, soup: BeautifulSoup) -> list:
        # Not used directly - we override parse() instead
        return []
