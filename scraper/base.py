"""Base scraper classes for LLM pricing extraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup


@dataclass
class ModelPricing:
    name: str                          # canonical model identifier, e.g. "gpt-4o"
    display_name: str                  # user-facing name, e.g. "GPT-4o"
    context_window: int                # tokens, or 0 if unknown
    max_output_tokens: Optional[int] = None
    input_price: float = 0.0           # in original currency (USD or CNY)
    cached_input_price: Optional[float] = None
    output_price: float = 0.0
    price_currency: str = "CNY"        # current currency of input/output fields written to JSON
    raw_input_price: Optional[float] = None
    raw_cached_input_price: Optional[float] = None
    raw_output_price: Optional[float] = None
    raw_price_currency: Optional[str] = None
    notes: Optional[str] = None
    tier: Optional[str] = None         # "pro", "lite", or None


@dataclass
class ScrapeResult:
    provider_id: str
    provider_name: str
    website: str
    pricing_page_url: str
    models: list = field(default_factory=list)
    error: Optional[str] = None


class BaseScraper(ABC):
    """Each provider subclasses this and implements parse_soup()."""

    provider_id: str
    provider_name: str
    website: str
    pricing_url: str
    currency: str = "USD"              # "USD" or "CNY"
    request_timeout: int = 30
    request_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36 llm-pricing-bot/1.0"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    def _build_session(self) -> requests.Session:
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retry)
        session = requests.Session()
        session.headers.update(self.request_headers)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def fetch_html(self) -> str:
        with self._build_session() as session:
            resp = session.get(self.pricing_url, timeout=self.request_timeout)
            resp.raise_for_status()
            return resp.text

    def parse(self, html: str) -> list:
        soup = BeautifulSoup(html, "html.parser")
        return self.parse_soup(soup)

    @abstractmethod
    def parse_soup(self, soup: BeautifulSoup) -> list:
        ...

    def run(self) -> ScrapeResult:
        try:
            html = self.fetch_html()
            models = self.parse(html)
            return ScrapeResult(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                website=self.website,
                pricing_page_url=self.pricing_url,
                models=models,
            )
        except Exception as e:
            return ScrapeResult(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                website=self.website,
                pricing_page_url=self.pricing_url,
                error=str(e),
            )

    @staticmethod
    def extract_price(text: str) -> Optional[float]:
        """Extract numeric price from text like '$0.14 / 1M tokens' or '¥1.00/百万token'."""
        import re
        text = text.replace(",", "").replace(" ", "").replace("~", "")
        # Try $0.14 or ¥1.00
        m = re.search(r'[¥$](\d+\.?\d*)', text)
        if m:
            return float(m.group(1))
        # Try bare numbers like "0.14"
        m = re.search(r'(\d+\.\d+)', text)
        if m:
            return float(m.group(1))
        return None

    @staticmethod
    def extract_context(text: str) -> int:
        """Parse '1M' -> 1000000, '128K' -> 128000, '131072' -> 131072."""
        import re
        text = text.upper().replace(" ", "").replace(",", "").replace("TOKENS", "")
        m = re.search(r'(\d+\.?\d*)\s*M', text)
        if m:
            return int(float(m.group(1)) * 1_000_000)
        m = re.search(r'(\d+\.?\d*)\s*K', text)
        if m:
            return int(float(m.group(1)) * 1_000)
        m = re.search(r'(\d+)', text)
        if m:
            return int(m.group(1))
        return 0


class PlaywrightMixin:
    """Override fetch_html() to use Playwright for JS-rendered pages."""

    playwright_timeout_ms: int = 60000
    playwright_wait_until: str = "domcontentloaded"
    playwright_wait_selector: Optional[str] = None
    playwright_wait_selector_timeout_ms: int = 20000
    playwright_post_wait_ms: int = 3000

    def fetch_html(self) -> str:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(
                self.pricing_url,
                wait_until=self.playwright_wait_until,
                timeout=self.playwright_timeout_ms,
            )
            if self.playwright_wait_selector:
                page.wait_for_selector(
                    self.playwright_wait_selector,
                    timeout=self.playwright_wait_selector_timeout_ms,
                )
            if self.playwright_post_wait_ms > 0:
                page.wait_for_timeout(self.playwright_post_wait_ms)
            html = page.content()
            browser.close()
            return html
