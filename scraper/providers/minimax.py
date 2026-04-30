"""MiniMax pricing scraper. JS-rendered page, requires Playwright."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing, PlaywrightMixin


class MinimaxScraper(PlaywrightMixin, BaseScraper):
    provider_id = "minimax"
    provider_name = "MiniMax"
    website = "https://www.minimaxi.com"
    pricing_url = "https://platform.minimaxi.com/document/Price"
    currency = "CNY"

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            # Look for header with model/pricing columns
            header_cells = rows[0].find_all(["td", "th"])
            header_text = " ".join(c.get_text(strip=True) for c in header_cells)

            if not any(kw in header_text for kw in ["模型", "价格", "输入", "输出", "计费", "Model", "Price"]):
                continue

            # Find columns
            name_col = input_col = output_col = None
            for i, h in enumerate(header_cells):
                ht = h.get_text(strip=True).lower()
                if "模型" in ht or "model" in ht or "型号" in ht:
                    name_col = i
                elif "输入" in ht:
                    input_col = i
                elif "输出" in ht:
                    output_col = i

            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < 3:
                    continue

                name = cells[name_col].get_text(strip=True) if name_col is not None and name_col < len(cells) else ""
                if not name or len(name) > 50:
                    continue

                input_price = self._parse_cny(cells[input_col].get_text(strip=True)) if input_col is not None and input_col < len(cells) else 0
                output_price = self._parse_cny(cells[output_col].get_text(strip=True)) if output_col is not None and output_col < len(cells) else 0

                if input_price == 0 and output_price == 0:
                    continue

                models.append(ModelPricing(
                    name=name.lower().replace(" ", "-"),
                    display_name=name,
                    context_window=0,
                    input_price=round(input_price, 2),
                    output_price=round(output_price, 2),
                ))

        return models

    @staticmethod
    def _parse_cny(text: str) -> float:
        text = text.replace(",", "").replace(" ", "").replace("元", "")
        m = re.search(r'[¥￥]?(\d+\.?\d*)', text)
        if m:
            val = float(m.group(1))
            if 0 < val < 0.1:  # likely per 1K tokens
                val *= 1000
            return val
        return 0.0
