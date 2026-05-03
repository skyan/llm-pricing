"""Qianwen (Alibaba Tongyi) pricing scraper."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from scraper.base import BaseScraper, ModelPricing


class QianwenScraper(BaseScraper):
    provider_id = "qianwen"
    provider_name = "Alibaba"
    website = "https://tongyi.aliyun.com"
    pricing_url = "https://help.aliyun.com/zh/model-studio/model-pricing"
    currency = "CNY"

    EXCLUDED_MODELS = {"qwen-plus", "qwen-flash"}

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models: dict[str, ModelPricing] = {}
        current_key: str | None = None

        for table in soup.find_all("table"):
            if not self._is_pricing_table(table):
                continue

            for row in table.find_all("tr")[1:]:
                texts = self._row_texts(row)
                if not texts:
                    continue

                model_id = self._extract_model_id(texts[0])
                if model_id and self._is_supported_model(model_id):
                    current_key = model_id
                    if current_key not in models:
                        models[current_key] = ModelPricing(
                            name=current_key,
                            display_name=self._format_display_name(current_key),
                            context_window=0,
                            input_price=0.0,
                            cached_input_price=None,
                            output_price=0.0,
                        )

                if current_key is None or current_key not in models:
                    continue

                range_text = self._find_range_text(texts)
                if range_text:
                    models[current_key].context_window = max(
                        models[current_key].context_window,
                        self._parse_context(range_text),
                    )

                prices = [self._parse_cny(text) for text in texts if "元" in text]
                prices = [price for price in prices if price > 0]
                if not prices:
                    continue

                if models[current_key].input_price == 0:
                    models[current_key].input_price = round(prices[0], 3)
                if models[current_key].output_price == 0 and len(prices) > 1:
                    models[current_key].output_price = round(max(prices[1:]), 3)

        ordered = []
        for key, model in models.items():
            if model.input_price and model.output_price:
                ordered.append(model)
        return ordered

    def _is_supported_model(self, model_id: str) -> bool:
        if model_id in self.EXCLUDED_MODELS:
            return False
        if model_id in {"qwen3-max", "qwen3-max-preview"}:
            return True
        match = re.fullmatch(r"qwen3\.(\d+)-(plus|flash|max(?:-preview)?)", model_id)
        if not match:
            return False
        minor = int(match.group(1))
        return minor >= 6

    @staticmethod
    def _is_pricing_table(table) -> bool:
        first_row = table.find("tr")
        if not first_row:
            return False
        header_text = re.sub(r"\s+", " ", first_row.get_text(" ", strip=True))
        return (
            "模型名称" in header_text
            and "输入单价" in header_text
            and "输出单价" in header_text
        )

    @staticmethod
    def _row_texts(row) -> list[str]:
        return [
            re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()
            for cell in row.find_all(["th", "td"])
            if cell.get_text(" ", strip=True).strip()
        ]

    @staticmethod
    def _extract_model_id(text: str) -> str | None:
        match = re.search(r"(qwen[\w.-]+)", text.lower())
        if not match:
            return None
        model_id = match.group(1)
        if model_id.endswith("-us") or model_id.endswith("-latest"):
            return None
        return model_id

    @staticmethod
    def _find_range_text(texts: list[str]) -> str:
        for text in texts:
            if "Token" in text and "≤" in text:
                return text
        return ""

    @staticmethod
    def _parse_cny(text: str) -> float:
        text = text.replace(",", "").replace(" ", "").replace("元", "")
        match = re.search(r"(\d+\.?\d*)", text)
        if match:
            return float(match.group(1))
        return 0.0

    @staticmethod
    def _parse_context(text: str) -> int:
        text = text.replace(",", "").replace(" ", "")
        match = re.search(r"≤(\d+)([KM])", text, re.IGNORECASE)
        if not match:
            return 0
        value = int(match.group(1))
        unit = match.group(2).upper()
        if unit == "M":
            return value * 1_000_000
        return value * 1_024

    @staticmethod
    def _format_display_name(model_id: str) -> str:
        parts = []
        for part in model_id.split("-"):
            if part.startswith("qwen"):
                parts.append("Qwen" + part[4:])
            else:
                parts.append(part.capitalize())
        return "-".join(parts)
