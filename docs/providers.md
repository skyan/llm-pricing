# Provider 抓取技术方案

## 总览

| 厂商 | 数据源 | 方式 | 模型数 |
|------|--------|------|--------|
| OpenAI | `developers.openai.com/api/docs/pricing` | fetch | 10 |
| Anthropic | `platform.claude.com/docs/en/about-claude/pricing` | fetch | 11 |
| Google | `cloud.google.com/vertex-ai/generative-ai/pricing` | fetch | 18 |
| xAI | `docs.x.ai/docs/models` | Playwright | 3 |
| DeepSeek | `api-docs.deepseek.com/quick_start/pricing` | fetch | 2 |
| 千问 | `help.aliyun.com/zh/model-studio/getting-started/models` | fetch | 6 |
| 豆包 | `volcengine.com/docs/82379/1544106` | Playwright | 4 |
| 文心 | `cloud.baidu.com/doc/qianfan/s/wmh4sv6ya` | fetch | 8 |
| Kimi | `platform.kimi.com/docs/pricing/{slug}` | fetch | 2 |
| GLM | `bigmodel.cn/pricing` | Playwright | 6 |
| MiniMax | `platform.minimaxi.com/docs/guides/pricing-paygo` | fetch | 5 |

## 技术栈

```
scraper/
├── base.py          # BaseScraper (requests) + PlaywrightMixin
├── main.py          # 编排器：遍历厂商→抓取→汇率转换→写 JSON
├── config.yaml      # 厂商注册表（URL、货币、启用状态）
├── currency.py      # USD/CNY 汇率（open.er-api.com）
└── providers/       # 每个厂商一个文件
    ├── openai.py    # fetch: SSR table，区分 short/long context
    ├── anthropic.py # fetch: SSR table，$X / MTok 格式
    ├── google.py    # fetch: 静态 table，rowspan 处理
    ├── xai.py       # Playwright: SPA table，去重 reasoning/non-reasoning
    ├── deepseek.py  # fetch: Docusaurus table，td header
    ├── qianwen.py   # fetch: 对比表格，模型名去描述后缀
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
- 解析: rowspan 处理，多 table 匹配 pricing-table 类

### xAI
- URL: `docs.x.ai/docs/models`
- 方式: Playwright，Mintlify SPA
- 解析: Table 0 含模型定价，reasoning/non-reasoning 同价去重。不包含旧模型 (grok-4/3)

### DeepSeek
- URL: `api-docs.deepseek.com/quick_start/pricing`
- 方式: 直接 fetch，Docusaurus SSR
- 解析: 单 table，header 用 `<td>`，有 PRICING 分段行需特殊处理

### 千问 (Alibaba)
- URL: `help.aliyun.com/zh/model-studio/getting-started/models`
- 方式: 直接 fetch
- 解析: 前几个 table 为对比表格，模型列为 header，行为属性（上下文/输入/输出）。模型名含"适合复杂任务"等描述需 regex 切除

### 豆包 (ByteDance)
- URL: `volcengine.com/docs/82379/1544106`
- 方式: Playwright，React SPA
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
- 方式: Playwright，React SPA
- 解析: 42 个 table，按"输入长度"列筛选有效 table（列: 模型 | 条件 | 输入 | 输出 | 缓存）。排除视觉/语音/ASR 模型

### MiniMax
- URL: `platform.minimaxi.com/docs/guides/pricing-paygo`
- 方式: 直接 fetch
- 解析: Table 0，列: 模型 | 输入 | 输出 | 缓存读取 | 缓存写入

## 容错机制

- 单个厂商抓取异常 → `ScrapeResult.error` 记录错误信息
- 单个厂商返回 0 模型 → 从上次 `pricing.json` 中取该厂商数据复用
- 全部厂商失败 → 保留现有数据，不写入空文件
- Playwright 超时: 60s `domcontentloaded` + 5s buffer
