"""GLM (Zhipu) pricing scraper. JS SPA, needs Playwright."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing, PlaywrightMixin


class GLMScraper(PlaywrightMixin, BaseScraper):
    provider_id = "glm"
    provider_name = "智谱"
    website = "https://open.bigmodel.cn"
    pricing_url = "https://bigmodel.cn/pricing"
    currency = "CNY"
    playwright_wait_selector = "table"
    playwright_post_wait_ms = 2000
    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        tables = soup.find_all("table")
        if not tables:
            return models

        # Only use tables that have the standard pricing format:
        # [模型名称, 条件, input_price, output_price, cache_storage, cache_hit]
        # Filter by checking if the first data row's column 1 contains "输入长度"
        valid_tables = set()
        for i, table in enumerate(tables):
            rows = table.find_all("tr")
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    c1 = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    if "输入长度" in c1:
                        valid_tables.add(i)
                        break

        current_model = ""
        seen = set()

        for ti, table in enumerate(tables):
            if ti not in valid_tables:
                continue
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                texts = [c.get_text(strip=True) for c in cells]
                if not texts:
                    continue

                c0 = texts[0]

                # Skip header rows
                if c0 in ("模型名称", "模型", "Model"):
                    continue

                # New model row
                if c0 and len(c0) > 3 and not any(kw in c0 for kw in ["输入长度", "输入", "输出", "缓存"]):
                    if re.match(r'GLM', c0, re.IGNORECASE):
                        # Skip vision (V), voice, ASR, fine-tuned models
                        if re.search(r'GLM-\d.*[Vv]', c0) or "Voice" in c0 or "ASR" in c0:
                            current_model = "skip"
                        else:
                            current_model = self._normalize_model_name(c0)

                if not current_model or current_model == "skip" or current_model in seen:
                    continue

                if len(texts) < 3:
                    continue

                # Find prices from cells
                inp = self._parse_price(texts[2]) if len(texts) > 2 else 0
                out = self._parse_price(texts[3]) if len(texts) > 3 else 0
                cache = self._parse_price(texts[5]) if len(texts) > 5 else None

                if not inp or inp > 200:
                    continue

                models.append(ModelPricing(
                    name=current_model.lower().replace(" ", "-"),
                    display_name=current_model,
                    context_window=128000,
                    input_price=inp or 0,
                    cached_input_price=cache if cache and cache > 0 else None,
                    output_price=out if (out is not None and out > 0) else 0,
                    tier=self._detect_tier(current_model),
                ))
                seen.add(current_model)

        return models

    @staticmethod
    def _parse_price(text: str):
        text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
        text = text.replace(",", "").replace(" ", "").strip()
        if not text or text in ("-", "", "限时免费"):
            return None
        # Require price indicator for non-obvious numbers
        has_indicator = bool(re.search(r'[元¥]|/[MT]|[Tt]okens', text))
        m = re.search(r'(\d+\.?\d*)', text)
        if m:
            val = float(m.group(1))
            # If value is large (>50) and no price indicator, likely not a price
            if val > 50 and not has_indicator:
                return None
            return val
        return None

    @staticmethod
    def _detect_tier(name: str) -> str | None:
        normalized = name.lower()
        if any(key in normalized for key in ("flashx", "air", "turbo")):
            return "lite"
        match = re.match(r"glm-(\d+(?:\.\d+)?)", normalized)
        if match and float(match.group(1)) >= 4.7:
            return "pro"
        return None

    @staticmethod
    def _normalize_model_name(name: str) -> str:
        return re.sub(r"新品$", "", name).strip()
