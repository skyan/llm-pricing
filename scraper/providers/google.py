"""Google Vertex AI pricing scraper."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from scraper.base import BaseScraper, ModelPricing


class GoogleScraper(BaseScraper):
    provider_id = "google"
    provider_name = "Google"
    website = "https://ai.google.dev"
    pricing_url = "https://cloud.google.com/vertex-ai/generative-ai/pricing"
    currency = "USD"

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models: dict[str, ModelPricing] = {}

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            headers = [self._cell_text(cell) for cell in rows[0].find_all(["th", "td"])]
            if not self._is_relevant_table(headers):
                continue

            if self._is_tiered_token_table(headers):
                self._parse_tiered_token_table(rows[1:], models)
            elif self._is_simple_token_table(headers):
                self._parse_simple_token_table(rows[1:], models)

        return list(models.values())

    def _parse_tiered_token_table(self, rows, models: dict[str, ModelPricing]) -> None:
        current_display_name = ""

        for row in rows:
            texts = self._row_texts(row)
            if not texts:
                continue

            if len(texts) == 1 and self._looks_like_model_name(texts[0]):
                normalized = self._normalize_model_name(texts[0])
                current_display_name = normalized if self._should_keep_model(normalized) else ""
                continue

            if not current_display_name:
                continue

            entry = models.setdefault(
                self._slugify(current_display_name),
                ModelPricing(
                    name=self._slugify(current_display_name),
                    display_name=current_display_name,
                    context_window=self._infer_context(current_display_name),
                    input_price=0.0,
                    cached_input_price=None,
                    output_price=0.0,
                ),
            )

            row_label = texts[0]
            if self._is_primary_input_row(row_label) and entry.input_price == 0:
                entry.input_price = self._extract_usd(texts[1]) or 0.0
                cached = self._extract_usd(texts[3]) if len(texts) > 3 else None
                if cached is not None:
                    entry.cached_input_price = cached
            elif self._is_primary_output_row(row_label) and entry.output_price == 0:
                entry.output_price = self._extract_usd(texts[1]) or 0.0

    def _parse_simple_token_table(self, rows, models: dict[str, ModelPricing]) -> None:
        current_display_name = ""

        for row in rows:
            texts = self._row_texts(row)
            if not texts:
                continue

            if len(texts) == 1 and self._looks_like_model_name(texts[0]):
                normalized = self._normalize_model_name(texts[0])
                current_display_name = normalized if self._should_keep_model(normalized) else ""
                continue

            if not current_display_name:
                continue

            entry = models.setdefault(
                self._slugify(current_display_name),
                ModelPricing(
                    name=self._slugify(current_display_name),
                    display_name=current_display_name,
                    context_window=self._infer_context(current_display_name),
                    input_price=0.0,
                    cached_input_price=None,
                    output_price=0.0,
                ),
            )

            row_label = texts[0]
            if self._is_simple_input_row(row_label) and entry.input_price == 0:
                entry.input_price = self._extract_usd(texts[1]) or 0.0
            elif self._is_simple_output_row(row_label) and entry.output_price == 0:
                entry.output_price = self._extract_usd(texts[1]) or 0.0

    @staticmethod
    def _row_texts(row) -> list[str]:
        return [
            re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()
            for cell in row.find_all(["th", "td"])
            if cell.get_text(" ", strip=True).strip()
        ]

    @staticmethod
    def _cell_text(cell) -> str:
        return re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()

    @staticmethod
    def _is_relevant_table(headers: list[str]) -> bool:
        if not headers:
            return False
        if headers[0] not in {"模型", "型号"}:
            return False

        header_text = " ".join(headers)
        if "价格" not in header_text:
            return False
        if any(keyword in header_text for keyword in ["功能", "存储", "训练", "Embedding", "嵌入"]):
            return False
        return True

    @staticmethod
    def _is_tiered_token_table(headers: list[str]) -> bool:
        header_text = " ".join(headers)
        return "缓存 输入" in header_text

    @staticmethod
    def _is_simple_token_table(headers: list[str]) -> bool:
        return headers[:4] == ["模型", "类型", "价格", "使用 Batch API 的价格"]

    @staticmethod
    def _looks_like_model_name(text: str) -> bool:
        return text.startswith("Gemini")

    @staticmethod
    def _normalize_model_name(text: str) -> str:
        name = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
        replacements = {
            "预览版": "Preview",
            "图片": "Image",
            "计算机使用": "Computer Use",
        }
        for source, target in replacements.items():
            name = name.replace(source, target)
        name = name.replace(" - ", " ")
        name = re.sub(r"\s+", " ", name).strip()
        return name

    @staticmethod
    def _should_keep_model(name: str) -> bool:
        lower = name.lower()
        if not lower.startswith("gemini"):
            return False
        if any(keyword in lower for keyword in ["embedding", "gemma", "1.5", "1.0"]):
            return False
        if any(keyword in lower for keyword in ["customer preference", "translation", "tool", "duration"]):
            return False
        if "image" in lower:
            return False
        return True

    @staticmethod
    def _is_primary_input_row(label: str) -> bool:
        return label.startswith("输入（") or label == "100 万个输入文本 token"

    @staticmethod
    def _is_primary_output_row(label: str) -> bool:
        return label.startswith("文本输出") or label == "100 万个输出文本 token"

    @staticmethod
    def _is_simple_input_row(label: str) -> bool:
        return label in {"100 万个输入 token", "100 万个输入文本 token"}

    @staticmethod
    def _is_simple_output_row(label: str) -> bool:
        return label == "100 万个输出文本 token"

    @staticmethod
    def _extract_usd(text: str) -> float | None:
        text = text.replace(",", "").replace(" ", "")
        match = re.search(r"\$?(\d+\.?\d*)", text)
        if not match:
            return None
        return float(match.group(1))

    @staticmethod
    def _infer_context(name: str) -> int:
        lower = name.lower()
        if any(keyword in lower for keyword in ["2.5", "2.0", "live api"]):
            return 1_000_000
        return 128_000

    @staticmethod
    def _slugify(name: str) -> str:
        slug = name.lower()
        slug = slug.replace(" ", "-")
        slug = slug.replace("/", "-")
        slug = re.sub(r"[^a-z0-9.-]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")
