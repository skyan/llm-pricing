# Provider 抓取技术方案

## 总览

| 厂商 | 数据源 | 方式 | 模型数 |
|------|--------|------|--------|
| OpenAI | `developers.openai.com/api/docs/pricing` | fetch | 10 |
| Anthropic | `platform.claude.com/docs/en/about-claude/pricing` | fetch | 11 |
| Google | `cloud.google.com/vertex-ai/generative-ai/pricing` | fetch | 11 |
| xAI | `docs.x.ai/developers/models` | fetch 优先，必要时 Playwright 回退 | 5 |
| DeepSeek | `api-docs.deepseek.com/zh-cn/quick_start/pricing` | fetch | 2 |
| 千问 | `help.aliyun.com/zh/model-studio/model-pricing` | fetch | 6 |
| 豆包 | `volcengine.com/docs/82379/1544106` | Playwright（等待表格出现） | 4 |
| 文心 | `cloud.baidu.com/doc/qianfan/s/wmh4sv6ya` | fetch | 8 |
| Kimi | `platform.kimi.com/docs/pricing/{slug}` | fetch | 2 |
| GLM | `bigmodel.cn/pricing` | Playwright（等待表格出现） | 6 |
| MiniMax | `platform.minimaxi.com/docs/guides/pricing-paygo` | fetch | 5 |

## 技术栈

```
scraper/
├── base.py          # BaseScraper (requests) + PlaywrightMixin
├── main.py          # 编排器：遍历厂商→抓取→保留原币值→汇率转换→写 JSON
├── config.yaml      # 厂商注册表（URL、货币、启用状态）
├── currency.py      # USD/CNY 汇率（open.er-api.com）
└── providers/       # 每个厂商一个文件
    ├── openai.py    # fetch: SSR table，区分 short/long context
    ├── anthropic.py # fetch: SSR table，$X / MTok 格式
    ├── google.py    # fetch: 按不同 pricing table 结构分别解析
    ├── xai.py       # fetch 优先 + Playwright 回退，优先读内嵌 metadata
    ├── deepseek.py  # fetch: Docusaurus table，td header
    ├── qianwen.py   # fetch: 官方计费页，按主型号提取首档价格
    ├── doubao.py    # Playwright: SPA table，零宽字符清洗
    ├── ernie.py     # fetch: rowspan + 千tokens→百万 ×1000
    ├── kimi.py      # fetch: 多子页面，正则提取价格
    ├── glm.py       # Playwright: 多表格，"输入长度"筛选纯文本模型
    └── minimax.py   # fetch: SSR table，5 个模型
```

## 各厂商细节

### OpenAI
- URL: `developers.openai.com/api/docs/pricing`
- 方式: 直接 fetch，SSR 渲染
- 解析: Table 0 为标准按量计费，取 GPT-5.x 系列，short context 列 (≤256K) 和 long context 列 (>256K) 分开两条

### Anthropic
- URL: `platform.claude.com/docs/en/about-claude/pricing`
- 方式: 直接 fetch，SSR 渲染
- 解析: Table 0，跳过 deprecated 模型。列: Model | Input | Cache Write | Cache Hit | Output

### Google
- URL: `cloud.google.com/vertex-ai/generative-ai/pricing`
- 方式: 直接 fetch，静态 HTML
- 解析: 只取 Gemini 文本模型，按两类 table 分开处理：`2.5/3.x` 的 tiered token 表与 `2.0` 的 simple token 表。跳过 grounding / cache storage / embedding / image-only 表

### xAI
- URL: `docs.x.ai/developers/models`
- 方式: 先直接 fetch；如果拿到的 HTML 还没渲染出定价内容，再回退 Playwright
- 解析: 优先读取页面内嵌的 `languageModels` 元数据，只保留带 input/output 的 Grok 文本模型；同一基础型号优先保留 reasoning 版本

### DeepSeek
- URL: `api-docs.deepseek.com/zh-cn/quick_start/pricing`
- 方式: 直接 fetch，Docusaurus SSR
- 解析: 以中文定价页为准，单 table，header 用 `<td>`，有 PRICING 分段行需特殊处理；价格直接按人民币抓取，不做 USD→CNY 转换

### 千问 (Alibaba)
- URL: `help.aliyun.com/zh/model-studio/model-pricing`
- 方式: 直接 fetch
- 解析: 改为官方计费页，按 table 顺序提取中国内地的主型号首档价格，并忽略 `-latest` / 日期版本 / `-us` 变体

### 豆包 (ByteDance)
- URL: `volcengine.com/docs/82379/1544106`
- 方式: Playwright，等待 `table` 出现后再取页面，避免固定 sleep
- 解析: Table 0，单元格含 `\u200b` 零宽字符需 strip。只取 doubao-seed-2.0 系列，排除 seedance/seedream 等视频/图片模型

### 文心 (Baidu)
- URL: `cloud.baidu.com/doc/qianfan/s/wmh4sv6ya`
- 方式: 直接 fetch
- 解析: 复杂 rowspan table，"元/千tokens" 单位行有 rowspan，后续行需 flag 跟踪。价格 ×1000 转为元/百万 tokens

### Kimi (Moonshot)
- URL: `platform.kimi.com/docs/pricing/{slug}` (chat-k26, chat-k25, chat-k2)
- 方式: 直接 fetch，Next.js SSR
- 解析: 分页抓取，正则 `¥(\d+\.?\d*)` 从 HTML 直接提取。K2.6/K2.5 单模型页，K2 多 variant 页

### GLM (Zhipu)
- URL: `bigmodel.cn/pricing`
- 方式: Playwright，等待 `table` 出现后再取页面，避免固定 sleep
- 解析: 42 个 table，按"输入长度"列筛选有效 table（列: 模型 | 条件 | 输入 | 输出 | 缓存）。排除视觉/语音/ASR 模型

### MiniMax
- URL: `platform.minimaxi.com/docs/guides/pricing-paygo`
- 方式: 直接 fetch
- 解析: Table 0，列: 模型 | 输入 | 输出 | 缓存读取 | 缓存写入

## 容错机制

- 单个厂商抓取异常 → `ScrapeResult.error` 记录错误信息
- 单个厂商返回 0 模型 → 从上次 `pricing.json` 中取该厂商数据复用
- 全部厂商失败 → 保留现有数据，不写入空文件
- fetch 请求: `requests.Session + Retry`，对 429/5xx 自动重试
- Playwright 超时: 默认 60s `domcontentloaded`，并优先等待目标 selector，而不是盲等固定秒数

## 价格语义

- 抓取器先产出厂商原始币种价格
- 对美元厂商，站点展示值统一换算为人民币
- DeepSeek 以中文页人民币价格为准，不属于美元厂商
- 写入 JSON 时同时保留 `raw_*` 原币值和 `raw_price_currency`
- 历史趋势按原币值去重，前端再按当前汇率归一化展示，避免纯汇率波动被误判为厂商调价
