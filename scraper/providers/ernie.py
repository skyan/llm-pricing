"""ERNIE (Baidu Qianfan) pricing scraper. Server-rendered HTML with multiple tables.

Prices are in 元/千tokens (CNY per 1K tokens). Must multiply by 1000 for 1M.
"""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class ErnieScraper(BaseScraper):
    provider_id = "ernie"
    provider_name = "ERNIE"
    website = "https://yiyan.baidu.com"
    pricing_url = "https://cloud.baidu.com/doc/qianfan/s/wmh4sv6ya"
    currency = "CNY"

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            # Check if this is a model pricing table
            header_text = " ".join(th.get_text(strip=True) for th in rows[0].find_all("th"))
            if "模型" not in header_text and "model" not in header_text.lower():
                continue

            headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]
            name_col = input_col = output_col = None
            for i, h in enumerate(headers):
                hl = h.lower()
                if "模型" in hl or "名称" in hl or "model" in hl:
                    name_col = i
                elif "输入" in hl or "input" in hl:
                    input_col = i
                elif "输出" in hl or "output" in hl:
                    output_col = i

            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue

                name = cells[name_col].get_text(strip=True) if name_col is not None and name_col < len(cells) else ""
                if not name or len(name) > 50:
                    continue

                input_price = self._parse_cny_per_k(cells[input_col].get_text(strip=True)) if input_col is not None and input_col < len(cells) else 0
                output_price = self._parse_cny_per_k(cells[output_col].get_text(strip=True)) if output_col is not None and output_col < len(cells) else 0

                if input_price == 0 and output_price == 0:
                    continue

                mid = re.sub(r'\(.*?\)', '', name).strip().lower().replace(" ", "-")
                models.append(ModelPricing(
                    name=mid, display_name=name, context_window=0,
                    input_price=round(input_price, 2), output_price=round(output_price, 2),
                ))

        return models

    @staticmethod
    def _parse_cny_per_k(text: str) -> float:
        """Parse CNY per 1000 tokens and convert to per 1M tokens."""
        text = text.replace(",", "").replace(" ", "").replace("元", "").replace("/千tokens", "")
        m = re.search(r'(\d+\.?\d*)', text)
        if m:
            val = float(m.group(1))
            # ERNIE prices are per 1K tokens, convert to per 1M
            if val > 0 and val < 100:
                return val * 1000
            return val
        return 0.0
