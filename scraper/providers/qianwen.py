"""Qianwen (Alibaba Tongyi) pricing scraper. Server-rendered comparison tables."""

import re
from bs4 import BeautifulSoup
from scraper.base import BaseScraper, ModelPricing


class QianwenScraper(BaseScraper):
    provider_id = "qianwen"
    provider_name = "Tongyi Qianwen"
    website = "https://tongyi.aliyun.com"
    pricing_url = "https://help.aliyun.com/zh/model-studio/getting-started/models"
    currency = "CNY"

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        seen = set()
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 3:
                continue

            # Check if this is a pricing comparison table
            header_text = rows[0].get_text(" ", strip=True)
            if "价格" not in header_text and "Token" not in header_text:
                # Check first row cells for model-like names
                hcells = rows[0].find_all(["td", "th"])
                is_pricing = False
                for c in hcells[1:]:
                    t = c.get_text(strip=True)
                    if any(kw in t for kw in ["Qwen", "千问", "适合", "能力"]):
                        is_pricing = True
                        break
                if not is_pricing:
                    continue

            # Parse: header has model names, rows have features
            hcells = rows[0].find_all(["td", "th"])
            model_names = []
            for c in hcells[1:]:
                name = self._clean_model_name(c.get_text(strip=True))
                if name:
                    model_names.append(name)

            if not model_names:
                continue

            # Data rows
            ctx_for_all = 0
            prices = {}

            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                label = cells[0].get_text(strip=True).lower() if cells else ""

                if "上下文" in label or "context" in label:
                    if len(cells) >= 2:
                        ctx_for_all = self._parse_context(cells[1].get_text(strip=True))

                elif "输入" in label and "价格" in label:
                    self._fill_prices(cells[1:], model_names, prices, "input")

                elif "输出" in label and "价格" in label:
                    self._fill_prices(cells[1:], model_names, prices, "output")

            # Build models
            for mname in model_names:
                if mname in seen:
                    continue
                seen.add(mname)
                p = prices.get(mname, {})
                inp = p.get("input", 0)
                out = p.get("output", 0)
                if inp == 0 and out == 0:
                    continue
                models.append(ModelPricing(
                    name=mname.lower().replace(" ", "-"),
                    display_name=mname,
                    context_window=ctx_for_all,
                    input_price=inp,
                    output_price=out,
                ))

        return models

    def _fill_prices(self, cells, model_names, prices, key):
        for i, cell in enumerate(cells):
            if i >= len(model_names):
                break
            text = cell.get_text(strip=True)
            p = self._parse_cny(text)
            if p > 0:
                prices.setdefault(model_names[i], {})[key] = round(p, 2)

    @staticmethod
    def _clean_model_name(text: str) -> str:
        # Remove descriptions like "适合复杂任务，能力最强"
        # Pattern: Latin/num ends, then Chinese description begins
        # e.g. "Qwen3.6-Max-Preview适合复杂任务，能力最强" -> "Qwen3.6-Max-Preview"
        # e.g. "千问Plus效果、速度、成本均衡" -> "千问Plus"
        text = re.sub(r'(适合|效果|能力|简单|速度快|极致|成本).*$', '', text)
        # Fix "千问Plus" -> "千问 Plus"
        text = re.sub(r'千问(?!\s)', '千问 ', text)
        return text.strip()

    @staticmethod
    def _parse_cny(text: str) -> float:
        text = text.replace(",", "").replace(" ", "").replace("元", "")
        m = re.search(r'(\d+\.?\d*)', text)
        if m:
            return float(m.group(1))
        return 0.0

    @staticmethod
    def _parse_context(text: str) -> int:
        text = text.replace(",", "").replace(" ", "")
        m = re.search(r'(\d+)万?', text)
        if m:
            val = int(m.group(1))
            if "万" in text:
                val *= 10000
            return val
        return 0
