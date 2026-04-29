# LLM Pricing Tracker

实时追踪各大 LLM 模型 API 定价，提供价格对比、历史趋势和搜索筛选功能。

**线上地址**: [https://llm-price.skyan.cc](https://llm-price.skyan.cc)

## 覆盖厂商

| 厂商 | 区域 | 数据来源 |
|------|------|----------|
| OpenAI | 海外 | platform.openai.com |
| Anthropic | 海外 | claude.com/pricing |
| Google | 海外 | cloud.google.com |
| xAI | 海外 | docs.x.ai |
| DeepSeek | 国内 | api-docs.deepseek.com |
| 通义千问 | 国内 | help.aliyun.com |
| 豆包 | 国内 | volcengine.com |
| 文心一言 | 国内 | cloud.baidu.com |
| Kimi | 国内 | platform.kimi.com |
| GLM | 国内 | open.bigmodel.cn |
| MiniMax | 国内 | platform.minimaxi.com |

## 架构设计

```
GitHub Action (每日定时) → Python 爬虫 → data/pricing.json
                                              ↓
                              Cloudflare Pages 自动部署
                                              ↓
                              llm-price.skyan.cc
```

- **数据采集**: Python 爬虫，支持 BeautifulSoup 静态解析 + Playwright JS 渲染
- **数据存储**: JSON 文件存储在仓库中，通过 GitHub Action 自动提交
- **前端**: 纯静态页面，Vanilla JS 无框架依赖
- **部署**: Cloudflare Pages，全球 CDN 加速

## 功能特性

- **价格展示**: 所有价格统一为人民币/百万 tokens，USD 按当日汇率转换
- **多维搜索**: 支持按模型名称、厂商名称搜索
- **厂商筛选**: 点击厂商标签快速过滤
- **列排序**: 点击表头按任意列排序（升序/降序）
- **历史趋势**: 内联 SVG 迷你图表展示价格变化趋势
- **响应式**: 适配桌面端和移动端
- **每日更新**: GitHub Action 每天自动抓取最新定价

## 本地开发

```bash
# 安装依赖
pip install -r requirements.txt
playwright install chromium

# 运行爬虫
python -m scraper.main

# 查看数据
cat data/pricing.json

# 启动本地服务器查看前端
python3 -m http.server 8080
# 浏览器打开 http://localhost:8080
```

## 项目结构

```
llm-pricing/
├── .github/workflows/scrape.yml    # GitHub Action 定时任务
├── scraper/
│   ├── main.py                     # 爬虫编排器
│   ├── base.py                     # 基础爬虫类 (BaseScraper + PlaywrightMixin)
│   ├── config.yaml                 # 厂商配置（可扩展）
│   ├── currency.py                 # USD/CNY 汇率获取
│   └── providers/                  # 各厂商爬虫实现
│       ├── __init__.py             # 爬虫注册表
│       ├── openai.py
│       ├── anthropic.py
│       ├── google.py
│       ├── xai.py
│       ├── deepseek.py
│       ├── qianwen.py
│       ├── doubao.py
│       ├── ernie.py
│       ├── kimi.py
│       ├── glm.py
│       └── minimax.py
├── data/
│   ├── pricing.json                # 最新定价数据
│   └── history/summary.json        # 90天历史趋势
├── css/style.css                   # 页面样式
├── js/app.js                       # 前端逻辑
├── index.html                      # 页面入口
└── requirements.txt                # Python 依赖
```

## 如何新增厂商

三步即可新增一个 LLM 厂商的价格追踪：

### Step 1: 编辑 `scraper/config.yaml`

在 `providers` 列表中添加新条目：

```yaml
  - id: newprovider           # 唯一标识符，与文件名一致
    name: "New Provider"      # 显示名称
    pricing_url: "https://example.com/pricing"
    website: "https://example.com"
    currency: USD             # USD 或 CNY
    enabled: true             # false 可临时禁用
```

### Step 2: 创建爬虫文件 `scraper/providers/newprovider.py`

```python
from scraper.base import BaseScraper, ModelPricing
from bs4 import BeautifulSoup

class NewProviderScraper(BaseScraper):
    provider_id = "newprovider"
    provider_name = "New Provider"
    website = "https://example.com"
    pricing_url = "https://example.com/pricing"
    currency = "USD"

    def parse_soup(self, soup: BeautifulSoup) -> list:
        models = []
        # TODO: 实现解析逻辑
        # 找到定价表格，提取模型名称、上下文长度、价格
        table = soup.find("table")
        if not table:
            return models

        for row in table.find_all("tr")[1:]:  # skip header
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            name = cells[0].get_text(strip=True)
            models.append(ModelPricing(
                name=name.lower().replace(" ", "-"),
                display_name=name,
                context_window=self.extract_context(cells[1].get_text(strip=True)),
                input_price=self.extract_price(cells[2].get_text(strip=True)) or 0,
                output_price=self.extract_price(cells[3].get_text(strip=True)) or 0,
            ))
        return models
```

**如果目标页面是 JS 渲染的 SPA**，使用 PlaywrightMixin：

```python
from scraper.base import BaseScraper, ModelPricing, PlaywrightMixin

class NewProviderScraper(PlaywrightMixin, BaseScraper):
    # ... 其余相同
```

### Step 3: 注册爬虫

在 `scraper/providers/__init__.py` 中添加：

```python
from scraper.providers.newprovider import NewProviderScraper

ALL_SCRAPERS["newprovider"] = NewProviderScraper
```

完成后运行 `python -m scraper.main` 验证新厂商数据是否正确抓取。

### 爬虫基类参考

| 方法 | 说明 |
|------|------|
| `extract_price(text)` | 从文本中提取价格数字，支持 "$0.14"、"¥1.00" 等格式 |
| `extract_context(text)` | 解析上下文长度，支持 "128K"、"1M"、"131072" 等格式 |
| `fetch_html()` | 获取页面 HTML（BaseScraper 用 requests，PlaywrightMixin 用浏览器） |
| `parse_soup(soup)` | 从 BeautifulSoup 对象中提取 ModelPricing 列表 |

## 数据格式

`data/pricing.json` 示例：

```json
{
  "last_updated": "2026-04-29T08:00:00Z",
  "usd_to_cny_rate": 7.25,
  "providers": [{
    "id": "openai",
    "name": "OpenAI",
    "website": "https://platform.openai.com",
    "pricing_page_url": "https://platform.openai.com/docs/pricing",
    "models": [{
      "name": "gpt-4o",
      "display_name": "GPT-4o",
      "context_window": 128000,
      "input_price": 18.20,
      "cached_input_price": 9.10,
      "output_price": 72.80,
      "notes": null
    }]
  }]
}
```

所有价格单位：**人民币元 / 1M tokens**。USD 价格在抓取时按当日汇率自动转换。

## License

MIT
