"""OpenAI pricing scraper. Uses public pricing API since openai.com blocks scraping."""

import json
import urllib.request
import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class OpenAIScraper(BaseScraper):
    provider_id = "openai"
    provider_name = "OpenAI"
    website = "https://platform.openai.com"
    pricing_url = "https://platform.openai.com/docs/pricing"
    currency = "USD"

    # Public pricing API (community-maintained)
    API_URL = "https://bes-dev.github.io/openai-pricing-api/api.json"

    def fetch_html(self) -> str:
        return ""  # Not used

    def parse_soup(self, soup: BeautifulSoup) -> list:
        return self._fetch_and_parse()

    def _fetch_and_parse(self) -> list:
        models = []
        try:
            req = urllib.request.Request(self.API_URL)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except Exception:
            return models

        # Data format: {models: {model_key: {model, pricing_type, category, ...}}, timestamp: ...}
        models_data = data.get("models", {}) if isinstance(data, dict) else {}

        context_map = {
            "gpt-5": 400000, "gpt-5.4": 256000, "gpt-5.5": 400000,
            "gpt-4o": 128000, "gpt-4.1": 1048576,
            "o5": 400000, "o4-pro": 200000, "o4-mini": 200000,
            "o3": 200000, "o1": 200000,
        }

        seen = set()
        for key, info in models_data.items():
            if not isinstance(info, dict):
                continue
            cat = info.get("category", "")
            if cat not in ("language_model", "reasoning"):
                continue

            name = info.get("model", key)
            # Clean context-length suffixes from name
            name = re.sub(r'\s*\([<>]\s*\d+[Kk].*?\)', '', name).strip()
            if name in seen:
                continue

            # Only keep GPT-5.x and o4/o5 series models
            if not self._is_current_gen(name):
                continue

            seen.add(name)

            inp = float(info.get("input", 0))
            out = float(info.get("output", 0))
            cached = info.get("cached_input")
            if cached is not None:
                cached = float(cached)

            if inp == 0 and out == 0:
                continue

            display = self._format_name(name)
            ctx = 128000
            for prefix, c in context_map.items():
                if name.startswith(prefix):
                    ctx = c
                    break

            models.append(ModelPricing(
                name=name,
                display_name=display,
                context_window=ctx,
                input_price=inp,
                cached_input_price=cached,
                output_price=out,
            ))

        return models

    @staticmethod
    def _is_current_gen(name: str) -> bool:
        """Only keep main GPT-5.x and o5/o4-pro series models."""
        n = name.lower()
        # Skip special variants
        if any(x in n for x in ("chat-latest", "codex", "search-api", "realtime", "audio", "transcribe")):
            return False
        if n.startswith("gpt-5"):
            return True
        if n.startswith("o5"):
            return True
        if n.startswith("o4-pro"):
            return True
        return False

    @staticmethod
    def _format_name(name: str) -> str:
        # e.g. "gpt-5.4-pro" -> "GPT-5.4 Pro"
        name = name.replace("_", " ")
        parts = name.split("-")
        result = []
        for p in parts:
            pu = p.upper()
            if pu in ("GPT", "O1", "O3", "O4", "O5"):
                result.append(pu if pu.startswith("O") else pu)
            elif pu in ("PRO", "MINI", "NANO", "TURBO"):
                result.append(p.capitalize())
            elif p and p[0].isdigit():
                result.append(pu)
            else:
                result.append(p.capitalize())
        return " ".join(result)
