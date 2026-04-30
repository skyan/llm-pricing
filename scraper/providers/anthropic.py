"""Anthropic pricing scraper. Card-based API pricing with Playwright for tab switching."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class AnthropicScraper(BaseScraper):
    provider_id = "anthropic"
    provider_name = "Anthropic"
    website = "https://www.anthropic.com"
    pricing_url = "https://claude.com/pricing"
    currency = "USD"

    def fetch_html(self) -> str:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.pricing_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            # Click API tab
            for tab in page.locator("button, a, [role=tab]").all():
                try:
                    if tab.inner_text().strip() == "API":
                        tab.click()
                        page.wait_for_timeout(3000)
                        break
                except Exception:
                    pass

            # Extract model-pricing pairs via DOM
            self._extracted = page.evaluate("""() => {
                const cards = [];
                document.querySelectorAll('h3, h4, [class*=heading]').forEach(el => {
                    const text = el.textContent.trim();
                    if (text.match(/opus 4[.]7|sonnet 4[.]6|haiku 4[.]5|opus 4[.]6|sonnet 4[.]5|opus 4[.]5|opus 4[.]1|sonnet 4\\b(?!\\.)|opus 4\\b(?!\\.)/i) && text.length < 40) {
                        const parent = el.closest('div')?.parentElement;
                        const pt = parent ? parent.textContent : '';
                        const prices = [];
                        const re = /\\$\\s*([\\d.]+)\\s*\\/\\s*MTok/g;
                        let m;
                        while ((m = re.exec(pt)) !== null) {
                            prices.push(parseFloat(m[1]));
                        }
                        if (prices.length >= 2) {
                            cards.push({model: text, prices: prices});
                        }
                    }
                });
                return cards;
            }""")

            html = page.content()
            browser.close()
            return html

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        extracted = getattr(self, "_extracted", [])

        for item in extracted:
            display = item["model"].strip()
            prices = item["prices"]

            inp = prices[0] if len(prices) > 0 else 0
            out = prices[1] if len(prices) > 1 else 0
            cache = prices[2] if len(prices) > 2 else None  # cache write

            models.append(ModelPricing(
                name="claude-" + display.lower().replace(" ", "-"),
                display_name="Claude " + display,
                context_window=200000,
                input_price=inp,
                cached_input_price=cache,
                output_price=out,
            ))

        return models
