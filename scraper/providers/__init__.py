"""Provider scrapers registry. Add new scrapers here."""

from scraper.providers.openai import OpenAIScraper
from scraper.providers.anthropic import AnthropicScraper
from scraper.providers.google import GoogleScraper
from scraper.providers.xai import XaiScraper
from scraper.providers.deepseek import DeepseekScraper
from scraper.providers.qianwen import QianwenScraper
from scraper.providers.doubao import DoubaoScraper
from scraper.providers.ernie import ErnieScraper
from scraper.providers.kimi import KimiScraper
from scraper.providers.glm import GLMScraper
from scraper.providers.minimax import MinimaxScraper

ALL_SCRAPERS = {
    "openai": OpenAIScraper,
    "anthropic": AnthropicScraper,
    "google": GoogleScraper,
    "xai": XaiScraper,
    "deepseek": DeepseekScraper,
    "qianwen": QianwenScraper,
    "doubao": DoubaoScraper,
    "ernie": ErnieScraper,
    "kimi": KimiScraper,
    "glm": GLMScraper,
    "minimax": MinimaxScraper,
}
