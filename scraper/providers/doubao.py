"""Doubao (ByteDance Volcengine) pricing scraper. JS-rendered, needs Playwright."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing, PlaywrightMixin


class DoubaoScraper(PlaywrightMixin, BaseScraper):
    provider_id = "doubao"
    provider_name = "ByteDance"
    website = "https://www.volcengine.com/product/doubao"
    pricing_url = "https://www.volcengine.com/docs/82379/1544106"
    currency = "CNY"
    playwright_wait_selector = "table"
    playwright_post_wait_ms = 4000

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        tables = soup.find_all("table")
        if not tables:
            return models

        # Table 0 is the main LLM pricing table
        table = tables[0]
        rows = table.find_all("tr")
        if len(rows) < 2:
            return models

        current_model = ""
        seen = set()

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            # Strip zero-width characters
            texts = [re.sub(r'[\u200b\u200c\u200d\ufeff]', '', c.get_text(strip=True)) for c in cells]
            if not texts:
                continue

            # Check if first cell has a model name
            c0 = texts[0]
            if c0 and len(c0) > 3 and not c0.startswith(("输入", "输出", "缓存", "TPM", "条件")):
                # Only keep doubao-seed-2.0 models (exclude seedance/seedream/embedding and non-doubao models)
                if any(kw in c0 for kw in ["seedance", "seedream", "seed3d", "embedding", "hyper3d", "hitem3d"]):
                    current_model = ""
                    continue
                # Skip non-doubao models listed on Volcengine (GLM, DeepSeek)
                if not c0.lower().startswith("doubao"):
                    current_model = "skip"
                    continue
                # Only keep seed-2.0 series
                if "seed-2.0" not in c0:
                    current_model = "skip"
                    continue
                current_model = c0

            if not current_model or current_model == "skip" or current_model in seen:
                continue

            if len(texts) < 3:
                continue

            # Find prices: input, cache_input, output
            # Table structure: 模型名称 | 条件 | 输入 | 缓存存储 | 缓存输入 | 输出
            # Column indices are roughly: 0=model, 1=condition, 2=input, 3=cache_storage, 4=cache_input, 5=output
            inp = self._parse_price(texts[2]) if len(texts) > 2 else None
            cache = self._parse_price(texts[4]) if len(texts) > 4 else None
            out = self._parse_price(texts[5]) if len(texts) > 5 else None

            if inp is None:
                continue

            models.append(ModelPricing(
                name=current_model.lower().replace(" ", "-"),
                display_name=current_model,
                context_window=256000,
                input_price=inp,
                cached_input_price=cache,
                output_price=out or 0,
            ))
            seen.add(current_model)

        return models

    @staticmethod
    def _parse_price(text: str):
        # Strip zero-width chars, commas, spaces
        text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
        text = text.replace(",", "").replace(" ", "").strip()
        if not text or text in ("-", "", "暂不支持", "不支持"):
            return None
        m = re.search(r'(\d+\.?\d*)', text)
        if m:
            return float(m.group(1))
        return None
