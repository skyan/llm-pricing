"""DeepSeek pricing scraper. Static Docusaurus page with a clean table."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class DeepseekScraper(BaseScraper):
    provider_id = "deepseek"
    provider_name = "DeepSeek"
    website = "https://api-docs.deepseek.com"
    pricing_url = "https://api-docs.deepseek.com/quick_start/pricing"
    currency = "USD"

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        article = soup.find("article") or soup.find(class_="markdown")
        if not article:
            return models

        tables = article.find_all("table")
        if not tables:
            return models

        table = tables[0]
        rows = table.find_all("tr")

        # DeepSeek table: first row is header with model names
        # First column = feature name, remaining columns = per-model values
        header_cells = rows[0].find_all("th")
        model_names = []
        for th in header_cells[1:]:  # skip first "MODEL" header
            text = th.get_text(strip=True)
            text = re.sub(r'\(.*?\)', '', text).strip()  # remove footnotes
            model_names.append(text)

        # Parse pricing rows
        prices = {}  # model_name -> {cache_hit, cache_miss, output}
        context_windows = {}  # model_name -> int
        max_outputs = {}  # model_name -> int

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True).lower()
            label_clean = re.sub(r'\(.*?\)', '', label).strip()

            for i, cell in enumerate(cells[1:]):
                if i >= len(model_names):
                    break
                mname = model_names[i]
                text = cell.get_text(strip=True)

                if "context" in label_clean or "上下文" in label_clean:
                    context_windows[mname] = self.extract_context(text)
                elif "max output" in label_clean or "最大输出" in label_clean:
                    max_outputs[mname] = self.extract_context(text)
                elif "cache hit" in label_clean or "缓存命中" in label_clean:
                    prices.setdefault(mname, {})["cache_hit"] = self.extract_price(text)
                elif "cache miss" in label_clean or ("input" in label_clean and "cache miss" not in label_clean):
                    prices.setdefault(mname, {})["input"] = self.extract_price(text)
                elif "output" in label_clean and "max" not in label_clean:
                    prices.setdefault(mname, {})["output"] = self.extract_price(text)

        for mname in model_names:
            if not mname:
                continue
            p = prices.get(mname, {})
            models.append(ModelPricing(
                name=mname.lower().replace(" ", "-"),
                display_name=mname,
                context_window=context_windows.get(mname, 0),
                max_output_tokens=max_outputs.get(mname) if mname in max_outputs else None,
                input_price=p.get("input", p.get("cache_miss", 0)),
                cached_input_price=p.get("cache_hit"),
                output_price=p.get("output", 0),
            ))

        return models
