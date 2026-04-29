"""Doubao (ByteDance Volcengine) pricing scraper. JS-rendered SPA, needs Playwright."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing, PlaywrightMixin


class DoubaoScraper(PlaywrightMixin, BaseScraper):
    provider_id = "doubao"
    provider_name = "Doubao"
    website = "https://www.volcengine.com/product/doubao"
    pricing_url = "https://www.volcengine.com/docs/82379/1544106"
    currency = "CNY"

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            # Find header row
            header_row = None
            header_idx = -1
            for i, row in enumerate(rows):
                ths = row.find_all("th")
                if ths and len(ths) >= 3:
                    header_row = ths
                    header_idx = i
                    break

            if not header_row:
                continue

            headers = [th.get_text(strip=True) for th in header_row]
            # Map columns
            name_col = input_col = output_col = ctx_col = None
            for i, h in enumerate(headers):
                hl = h.lower()
                if "模型" in hl or "model" in hl:
                    name_col = i
                elif "输入" in hl and "缓存" not in hl:
                    input_col = i
                elif "输出" in hl:
                    output_col = i
                elif "上下文" in hl or "context" in hl:
                    ctx_col = i

            for row in rows[header_idx + 1:]:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue

                name = cells[name_col].get_text(strip=True) if name_col is not None and name_col < len(cells) else ""
                if not name or len(name) > 40:
                    continue

                input_price = 0.0
                output_price = 0.0
                ctx = 0
                if input_col is not None and input_col < len(cells):
                    input_price = self._parse_cny(cells[input_col].get_text(strip=True))
                if output_col is not None and output_col < len(cells):
                    output_price = self._parse_cny(cells[output_col].get_text(strip=True))
                if ctx_col is not None and ctx_col < len(cells):
                    ctx = self.extract_context(cells[ctx_col].get_text(strip=True))

                if input_price == 0 and output_price == 0:
                    continue

                mid = name.lower().replace(" ", "-")
                models.append(ModelPricing(
                    name=mid, display_name=name, context_window=ctx,
                    input_price=round(input_price, 2), output_price=round(output_price, 2),
                ))

        return models

    @staticmethod
    def _parse_cny(text: str) -> float:
        text = text.replace(",", "").replace(" ", "").replace("元", "")
        m = re.search(r'[¥￥]?(\d+\.?\d*)', text)
        if m:
            val = float(m.group(1))
            # If value seems like per 1K tokens, convert to per 1M
            if val < 0.1 and val > 0:
                val *= 1000
            return val
        return 0.0
