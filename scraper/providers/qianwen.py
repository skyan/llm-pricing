"""Qianwen (Alibaba Tongyi) pricing scraper. Server-rendered HTML tables."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class QianwenScraper(BaseScraper):
    provider_id = "qianwen"
    provider_name = "Tongyi Qianwen"
    website = "https://tongyi.aliyun.com"
    pricing_url = "https://help.aliyun.com/zh/model-studio/getting-started/models"
    currency = "CNY"

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            # Check if this table has pricing data
            header_text = " ".join(th.get_text(strip=True).lower() for th in rows[0].find_all("th"))
            if "价格" not in header_text and "price" not in header_text and "计费" not in header_text:
                if "模型" not in header_text and "model" not in header_text:
                    continue

            headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]
            # Map columns
            name_col = input_col = output_col = ctx_col = None
            for i, h in enumerate(headers):
                hl = h.lower()
                if "模型" in hl or "model" in hl:
                    name_col = i
                elif "输入" in hl or "input" in hl:
                    input_col = i
                elif "输出" in hl or "output" in hl:
                    output_col = i
                elif "上下文" in hl or "context" in hl or "长度" in hl:
                    ctx_col = i

            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue

                name = cells[name_col].get_text(strip=True) if name_col is not None and name_col < len(cells) else ""
                if not name or name in ("-", "模型名称"):
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

                # Alibaba sometimes prices per 1K tokens - convert to 1M
                # Prices in CNY per 1000 tokens would need *1000
                if input_price < 0.1 and input_price > 0:
                    input_price *= 1000
                if output_price < 0.1 and output_price > 0:
                    output_price *= 1000

                cleaned = re.sub(r'\(.*?\)', '', name).strip()
                mid = cleaned.lower().replace(" ", "-").replace("/", "-")

                models.append(ModelPricing(
                    name=mid,
                    display_name=cleaned,
                    context_window=ctx,
                    input_price=round(input_price, 2),
                    output_price=round(output_price, 2),
                ))

        return self._deduplicate(models)

    @staticmethod
    def _parse_cny(text: str) -> float:
        text = text.replace(",", "").replace(" ", "").replace("元", "").replace("~", "")
        # Try "¥X.XX" format
        m = re.search(r'[¥￥](\d+\.?\d*)', text)
        if m:
            return float(m.group(1))
        # Try bare number
        m = re.search(r'(\d+\.?\d*)', text)
        if m:
            return float(m.group(1))
        return 0.0

    @staticmethod
    def _deduplicate(models: list) -> list:
        seen = {}
        for m in models:
            if m.name in seen:
                existing = seen[m.name]
                if m.input_price > existing.input_price:
                    existing.input_price = m.input_price
                if m.output_price > existing.output_price:
                    existing.output_price = m.output_price
            else:
                seen[m.name] = m
        return list(seen.values())
