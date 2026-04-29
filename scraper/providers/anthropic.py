"""Anthropic pricing scraper. Card-based API pricing, needs Playwright for tab switching."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing, PlaywrightMixin


class AnthropicScraper(PlaywrightMixin, BaseScraper):
    provider_id = "anthropic"
    provider_name = "Anthropic"
    website = "https://www.anthropic.com"
    pricing_url = "https://claude.com/pricing"
    currency = "USD"

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        # Anthropic pricing is in cards, not tables
        # Look for price patterns like "$X / MTok" near model names
        text = soup.get_text(" ", strip=True)

        # Known model patterns and their context windows
        model_configs = [
            ("claude-opus-4-7", "Claude Opus 4.7", 200000),
            ("claude-sonnet-4-6", "Claude Sonnet 4.6", 200000),
            ("claude-haiku-4-5", "Claude Haiku 4.5", 200000),
            ("claude-opus-4-6", "Claude Opus 4.6", 200000),
            ("claude-sonnet-4-5", "Claude Sonnet 4.5", 200000),
            ("claude-opus-4-5", "Claude Opus 4.5", 200000),
            ("claude-opus-4-1", "Claude Opus 4.1", 200000),
            ("claude-sonnet-4", "Claude Sonnet 4", 200000),
            ("claude-opus-4", "Claude Opus 4", 200000),
        ]

        # Extract all dollar amounts near "MTok" (Anthropic's pricing unit)
        # Pattern: $X / MTok or $X.X / MTok
        price_matches = list(re.finditer(r'\$(\d+\.?\d*)\s*/\s*MTok', text))

        # Try to associate prices with models by proximity in the text
        # Strategy: find model cards and extract their prices
        for model_id, display_name, ctx in model_configs:
            # Try to find the model mentioned near a price
            search_name = model_id.replace("claude-", "").replace("-", " ")
            model_pos = text.lower().find(search_name)
            if model_pos == -1:
                continue

            # Look for prices near this model mention
            nearby = text[max(0, model_pos - 200):model_pos + 500]
            prices = re.findall(r'\$(\d+\.?\d*)\s*/\s*MTok', nearby)

            if len(prices) >= 2:
                input_price = float(prices[0])
                output_price = float(prices[-1])  # usually the highest
                # For Anthropic, cached input write = input * 1.25, read = input * 0.1
                cached_price = round(input_price * 1.25, 4)

                models.append(ModelPricing(
                    name=model_id,
                    display_name=display_name,
                    context_window=ctx,
                    input_price=input_price,
                    cached_input_price=cached_price,
                    output_price=output_price,
                ))

        # If the text-based approach failed to find specific models, try parsing cards
        if not models:
            # Find all elements that might be model cards
            cards = soup.find_all(["div", "section"], class_=re.compile(r"card|pricing|model", re.I))
            for card in cards:
                card_text = card.get_text(" ", strip=True)
                # Look for model name + pricing pattern
                if "$" not in card_text or "MTok" not in card_text:
                    continue

                prices = re.findall(r'\$(\d+\.?\d*)\s*/\s*MTok', card_text)
                if len(prices) < 2:
                    continue

                # Try to find model name in the card
                model_name = card_text.split("$")[0].strip().split("\n")[0].strip()
                if not model_name or len(model_name) > 50:
                    model_name = "Unknown"

                models.append(ModelPricing(
                    name=model_name.lower().replace(" ", "-"),
                    display_name=model_name,
                    context_window=200000,
                    input_price=float(prices[0]),
                    cached_input_price=round(float(prices[0]) * 1.25, 4),
                    output_price=float(prices[-1]),
                ))

        return models
