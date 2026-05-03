"""ERNIE (Baidu Qianfan) pricing scraper."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class ErnieScraper(BaseScraper):
    provider_id = "ernie"
    provider_name = "ERNIE"
    website = "https://yiyan.baidu.com"
    pricing_url = "https://cloud.baidu.com/doc/qianfan/s/wmh4sv6ya"
    currency = "CNY"

    EXCLUDED_FAMILY_KEYWORDS = ("Speed Pro", "Lite Pro", "Character")
    FAMILY_DEFAULT_CONTEXT = {
        "ERNIE 4.5 Turbo": 128000,
    }

    def parse_soup(self, soup: BeautifulSoup) -> list:
        text = soup.get_text("\n", strip=True)
        lines = [self._normalize_line(line) for line in text.splitlines()]
        start = self._find_text_postpaid_start(lines)
        if start is None:
            return []
        end = self._find_text_postpaid_end(lines, start)

        models = []
        i = start
        current_family = None
        while i < end:
            family_tier = self._family_tier(lines[i])
            if family_tier is not None:
                current_family = lines[i]
                i += 1
                if i >= end:
                    break
            elif lines[i].startswith("ERNIE "):
                current_family = None
                i += 1
                continue
            if current_family is None:
                i += 1
                continue
            if not lines[i].startswith("ERNIE-"):
                i += 1
                continue

            versions = []
            while i < end and lines[i].startswith("ERNIE-"):
                versions.append(lines[i])
                i += 1

            while i < end and lines[i] != "推理服务":
                if self._family_tier(lines[i]) is not None or lines[i] == "按量包付费":
                    break
                i += 1
            if i >= end or lines[i] != "推理服务":
                continue

            i += 1
            section_prices, i = self._parse_price_block(lines, i, end)
            if not versions or "input" not in section_prices or "output" not in section_prices:
                continue

            for version in versions:
                if self._skip_version(version):
                    continue
                display_name = version if current_family in {"ERNIE 4.5 Turbo", "ERNIE 4.5"} else current_family
                models.append(ModelPricing(
                    name=version.lower(),
                    display_name=display_name,
                    context_window=self._infer_context(version, current_family),
                    input_price=section_prices["input"],
                    cached_input_price=section_prices.get("cache"),
                    output_price=section_prices["output"],
                ))

        return models

    def _parse_price_block(self, lines: list[str], start: int, end: int) -> tuple[dict[str, float], int]:
        prices: dict[str, float] = {}
        i = start
        label_map = {
            "输入": "input",
            "命中缓存": "cache",
            "输出": "output",
        }

        while i < end:
            token = lines[i]
            if self._family_tier(token) is not None or token == "按量包付费" or token.startswith("DeepSeek-"):
                break
            if token.startswith("ERNIE-"):
                break

            key = None
            if token.startswith("输入"):
                key = "input"
            elif token == "命中缓存":
                key = "cache"
            elif token.startswith("输出"):
                key = "output"
            if key is None:
                i += 1
                continue

            i += 1
            value = None
            while i < end:
                token = lines[i]
                if (
                    token.startswith("输入")
                    or token == "命中缓存"
                    or token.startswith("输出")
                    or self._family_tier(token) is not None
                    or token == "按量包付费"
                    or token.startswith("ERNIE-")
                    or token.startswith("DeepSeek-")
                ):
                    break
                if re.fullmatch(r"\d+\.?\d*", token) and value is None:
                    value = self._to_per_million(float(token))
                if token.startswith("元/"):
                    i += 1
                    break
                i += 1
            if value is not None and key not in prices:
                prices[key] = value

        return prices, i

    @staticmethod
    def _find_text_postpaid_start(lines: list[str]) -> int | None:
        for i, line in enumerate(lines):
            if line != "按量后付费":
                continue
            for j in range(i + 1, len(lines)):
                if lines[j] == "按量包付费":
                    break
                if lines[j].startswith("ERNIE "):
                    return j
        return None

    @staticmethod
    def _find_text_postpaid_end(lines: list[str], start: int) -> int:
        for i in range(start, len(lines)):
            if lines[i] == "按量包付费":
                return i
        return len(lines)

    def _infer_context(self, version: str, family: str) -> int:
        match = re.search(r"-(\d+)K(?:-|$)", version, re.IGNORECASE)
        if match:
            return int(match.group(1)) * 1000
        return self.FAMILY_DEFAULT_CONTEXT.get(family, 0)

    def _family_tier(self, line: str) -> str | None:
        if not line.startswith("ERNIE "):
            return None
        if any(keyword in line for keyword in self.EXCLUDED_FAMILY_KEYWORDS):
            return None
        match = re.match(r"ERNIE\s+(\d+(?:\.\d+)?)", line)
        if not match:
            return None
        if float(match.group(1)) >= 4.5:
            return "pro"
        return None


    @staticmethod
    def _skip_version(version: str) -> bool:
        return (
            "-VL" in version
            or "Thinking" in version
            or version == "ERNIE-4.5-Turbo-20260402"
        )

    @staticmethod
    def _normalize_line(line: str) -> str:
        return re.sub(r"\s+", " ", line).strip()

    @staticmethod
    def _to_per_million(price_per_thousand: float) -> float:
        return round(price_per_thousand * 1000, 2)
