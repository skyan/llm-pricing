"""MiniMax pricing scraper. Direct fetch from platform.minimaxi.com docs."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class MinimaxScraper(BaseScraper):
    provider_id = "minimax"
    provider_name = "MiniMax"
    website = "https://www.minimaxi.com"
    pricing_url = "https://platform.minimaxi.com/docs/guides/pricing-paygo"
    currency = "CNY"

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
            if len(cells) < 3:
                continue

            name = cells[0].get_text(strip=True)
            if not name or not name.startswith("MiniMax") and not name.startswith("M2"):
                continue

            # Columns: 模型 | 输入 | 输出 | 缓存读取 | 缓存写入
            inp = self._parse_price(cells[1].get_text(strip=True))
            out = self._parse_price(cells[2].get_text(strip=True))
            cache_read = self._parse_price(cells[3].get_text(strip=True))

            if inp == 0 and out == 0:
                continue

            models.append(ModelPricing(
                name=name.lower().replace(" ", "-"),
                display_name=name,
                context_window=245760,
                input_price=inp,
                cached_input_price=cache_read if cache_read > 0 else None,
                output_price=out,
            ))

        return models

    @staticmethod
    def _parse_price(text: str) -> float:
        text = text.replace(",", "").replace(" ", "").strip()
        if not text or text in ("-", "", "——"):
            return 0.0
        m = re.search(r'(\d+\.?\d*)', text)
        return float(m.group(1)) if m else 0.0
