"""GLM (Zhipu) pricing scraper. Fully JS-rendered SPA, requires Playwright."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing, PlaywrightMixin


class GLMScraper(PlaywrightMixin, BaseScraper):
    provider_id = "glm"
    provider_name = "GLM"
    website = "https://open.bigmodel.cn"
    pricing_url = "https://open.bigmodel.cn/pricing"
    currency = "CNY"

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []

        # GLM page is an SPA - try to find pricing tables after rendering
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]
            if not headers:
                # Try first row cells
                headers = [td.get_text(strip=True) for td in rows[0].find_all("td")]

            name_col = input_col = output_col = None
            for i, h in enumerate(headers):
                hl = h.lower()
                if "模型" in hl or "model" in hl:
                    name_col = i
                elif "输入" in hl and "缓存" not in hl:
                    input_col = i
                elif "输出" in hl:
                    output_col = i

            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue

                name = cells[name_col].get_text(strip=True) if name_col is not None and name_col < len(cells) else ""
                if not name or len(name) > 40:
                    continue

                input_price = self._parse_cny(cells[input_col].get_text(strip=True)) if input_col is not None and input_col < len(cells) else 0
                output_price = self._parse_cny(cells[output_col].get_text(strip=True)) if output_col is not None and output_col < len(cells) else 0

                if input_price == 0 and output_price == 0:
                    continue

                mid = name.lower().replace(" ", "-").replace("/", "-")
                models.append(ModelPricing(
                    name=mid, display_name=name, context_window=0,
                    input_price=round(input_price, 2), output_price=round(output_price, 2),
                ))

        # If table parsing found nothing, try card-based layout
        if not models:
            text = soup.get_text(" ", strip=True)
            # Look for known GLM model patterns
            model_patterns = [
                ("glm-5", "GLM-5", 200000),
                ("glm-4-plus", "GLM-4 Plus", 128000),
                ("glm-4-air", "GLM-4 Air", 128000),
                ("glm-4-flash", "GLM-4 Flash", 128000),
                ("glm-4-long", "GLM-4 Long", 1000000),
            ]

            for mid, display, ctx in model_patterns:
                pos = text.lower().find(mid)
                if pos == -1:
                    continue
                nearby = text[max(0, pos - 200):pos + 500]
                prices = re.findall(r'[¥￥]?(\d+\.?\d*)\s*元?', nearby)
                prices = [float(p) for p in prices if float(p) > 0]
                if len(prices) >= 2:
                    sorted_p = sorted(set(prices))
                    models.append(ModelPricing(
                        name=mid, display_name=display, context_window=ctx,
                        input_price=round(sorted_p[0], 2),
                        output_price=round(sorted_p[-1], 2),
                    ))

        return models

    @staticmethod
    def _parse_cny(text: str) -> float:
        text = text.replace(",", "").replace(" ", "").replace("元", "")
        m = re.search(r'[¥￥]?(\d+\.?\d*)', text)
        if m:
            return float(m.group(1))
        return 0.0
