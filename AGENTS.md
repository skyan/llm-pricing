# Repo Conventions

- Scraper/provider code is the source of truth for factual data only: model inclusion, canonical names, prices, context windows, and raw currencies.
- UI-facing tier labels such as `pro` and `lite` are derived presentation rules by default and should be implemented in `js/app.js`, not hard-coded into scraper outputs, unless the user explicitly wants tier metadata persisted in generated JSON.
- When a request changes model scope (for example remove a model, rename a model, or fix price extraction), update scraper outputs and rebuild generated data.
- When a request only changes display categorization (for example `pro` vs `lite`), prefer changing frontend rules instead of re-scraping historical data.
