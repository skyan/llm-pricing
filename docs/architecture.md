# 架构设计

## 总览

```
GitHub Actions (每日定时) → Python 爬虫 → data/pricing.json + data/history/summary.json
                                            ├─ 提交回 Git 仓库
                                            └─ 上传每日快照到 Cloudflare R2
                                                                 ↓
                                                Cloudflare Pages 自动部署静态站点
                                                                 ↓
                                                     llm-price.skyan.cc
```

## 核心组成

- **数据采集**: Python 爬虫，支持 BeautifulSoup 静态解析 + Playwright JS 渲染
- **数据存储**: 仓库内保留最新定价与趋势汇总；每日全量快照长期存储在 Cloudflare R2，并据此重建 365 天趋势汇总
- **前端**: 纯静态页面，Vanilla JS 无框架依赖
- **部署**: Cloudflare Pages，全球 CDN 加速

## 数据职责

- [data/pricing.json](/Users/yanlin.sky/workspace/github.com/skyan/llm-pricing/data/pricing.json): 最近一次抓取的最新全量价格
- [data/history/summary.json](/Users/yanlin.sky/workspace/github.com/skyan/llm-pricing/data/history/summary.json): 最近 365 天趋势汇总，供前端直接读取
- `R2 history/YYYY-MM-DD.json`: 每日完整价格快照，用于长期归档与重建 `summary.json`
- `R2 history/index.json`: 已存在快照日期索引，避免重建时盲扫整段日期范围

## 更新流程

1. GitHub Actions 定时运行 [.github/workflows/scrape.yml](/Users/yanlin.sky/workspace/github.com/skyan/llm-pricing/.github/workflows/scrape.yml)。
2. [scraper/main.py](/Users/yanlin.sky/workspace/github.com/skyan/llm-pricing/scraper/main.py) 抓取各厂商价格并生成最新 [data/pricing.json](/Users/yanlin.sky/workspace/github.com/skyan/llm-pricing/data/pricing.json)。
3. workflow 将当天快照上传到 R2 的 `history/YYYY-MM-DD.json`，并同步更新 `history/index.json`。
4. [scripts/rebuild_summary_from_r2.py](/Users/yanlin.sky/workspace/github.com/skyan/llm-pricing/scripts/rebuild_summary_from_r2.py) 优先读取 `history/index.json`，只下载最近 365 天实际存在的快照来重建 [data/history/summary.json](/Users/yanlin.sky/workspace/github.com/skyan/llm-pricing/data/history/summary.json)。
5. Cloudflare Pages 基于仓库中的静态文件自动部署最新站点。
