"""ERNIE (Baidu Qianfan) pricing scraper. Rowspan-heavy HTML table."""

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
        tables = soup.find_all("table")
        if not tables:
            return []

        table = tables[0]
        rows = table.find_all("tr")

        current_family = ""
        in_token_section = False
        models = {}

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            texts = [c.get_text(strip=True) for c in cells]

            # Check for new model family
            first_cell = texts[0] if texts else ""
            if first_cell and first_cell.upper().startswith("ERNIE"):
                in_token_section = False
                if first_cell.startswith("ERNIE-"):
                    current_family = first_cell
                else:
                    parts = first_cell.split()
                    current_family = " ".join(parts[:3]) if len(parts) >= 3 else first_cell

            if not current_family:
                continue

            # Track whether we're in a token-pricing section (unit is "元/千tokens" with rowspan)
            if any("千tokens" in t or "千Token" in t for t in texts):
                in_token_section = True
            if any("元/次" in t or "元/个" in t or "元/万" in t or "元/张" in t for t in texts):
                in_token_section = False
                continue
            if not in_token_section:
                continue

            # Find the price column (first numeric like "0.xxx" or "x.xxx", not "-")
            price = None
            price_idx = -1
            for i, t in enumerate(texts):
                p = self._parse_price(t)
                if p is not None:
                    price = p
                    price_idx = i
                    break

            if price is None or price_idx <= 0:
                continue

            # The label is in the cell just before the price
            label = texts[price_idx - 1] if price_idx > 0 else ""

            # Convert from 元/千tokens to 元/1M tokens
            price = round(price * 1000, 2)

            # Categorize by label (check output before input since output labels may contain "输入")
            m = models.setdefault(current_family, {"in": 0, "cache": None, "out": 0})
            if "命中缓存" in label or "缓存" in label:
                m["cache"] = max(m.get("cache") or 0, price)
            elif "输出" in label:
                m["out"] = max(m["out"], price)
            elif "输入" in label:
                m["in"] = max(m["in"], price)

        result = []
        for family, p in models.items():
            if p["in"] == 0 and p["out"] == 0:
                continue
            result.append(ModelPricing(
                name=family.lower().replace(" ", "-"),
                display_name=family,
                context_window=128000,
                input_price=p["in"],
                cached_input_price=p.get("cache"),
                output_price=p["out"],
            ))

        return result

    @staticmethod
    def _parse_price(text: str):
        text = text.replace(",", "").replace(" ", "").strip()
        if not text or text in ("-", "", "免费"):
            return None
        m = re.search(r'^(\d+\.?\d*)$', text)
        if m:
            return float(m.group(1))
        return None
