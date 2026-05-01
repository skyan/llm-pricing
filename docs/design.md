# LLM Pricing Tracker Design Guide

## Purpose

This document defines the visual and interaction style for the `llm-pricing` site.
It is the source of truth for future UI refinements, logo updates, favicon changes,
and new page additions.

The product is a data-first pricing tracker rather than a marketing site. The design
should feel:

- calm
- readable
- compact
- trustworthy
- slightly editorial rather than overly technical

The site should prioritize fast scanning of model prices, trend changes, provider
grouping, and source links.

## Design Principles

### 1. Data First

The table is the product. Decorative elements should never compete with pricing,
trend, or provider information.

### 2. Low Noise

Avoid bright dashboard chrome, large gradients, floating cards, oversized badges,
or attention-grabbing hero sections. Most surfaces should stay quiet and neutral.

### 3. Professional, Not Corporate Generic

The UI should not look like a default admin template. The logo, icon palette, and
top header should provide a small amount of identity while the main workspace stays
restrained.

### 4. Chinese-First Readability

Typography, spacing, and line height should work well for mixed Chinese and English
text, model names, and token-related numeric data.

### 5. Stable Interaction

Sorting, filtering, trend expansion, and source links should feel predictable. Avoid
layout jumps, disappearing controls, or overly animated transitions.

## Layout System

### Overall Structure

The page uses a simple top-down workbench layout:

1. sticky header
2. compact controls area
3. pricing table
4. expandable trend detail row
5. lightweight footer

### Width and Spacing

- Main content max width: `1500px`
- Header horizontal padding: `24px`
- Main body padding: `16px 20px 60px`
- Control spacing: compact and dense, with small horizontal gaps

This is intentionally closer to an internal analysis tool than a promotional site.

### Header Behavior

The header stays sticky and acts as the persistent orientation layer.

It contains:

- logo mark
- Chinese product title
- English subtitle
- update timestamp
- currency conversion context

The header should remain visually light:

- white surface
- thin border
- small shadow
- no banner artwork

## Color System

### Core UI Palette

Defined in `css/style.css`:

- background: `#f5f6f8`
- surface: `#ffffff`
- border: `#e5e7eb`
- primary text: `#1a1a2e`
- secondary text: `#6b7280`
- accent blue: `#2563eb`
- accent background: `#eff6ff`
- lower price / stable positive tone: `#059669`
- higher price / warning tone: `#dc2626`

### Usage Rules

- Blue is the main interaction accent for active filters, sorting state, and focus.
- Red is reserved for output-price trend lines that move upward or visually signal
  higher pricing pressure.
- Green is reserved for lower or downward trend signals.
- Neutral grays should carry most layout structure.

### Brand Palette

The current logo and favicon use a Renaissance-inspired palette rather than a neon
tech palette.

Current logo palette:

- parchment background
- warm stone borders
- muted gold columns
- desaturated blue / sage / brown trend line
- dark brown nodes

This palette should remain soft, painterly, and slightly historical in tone.

Avoid:

- neon gradients
- cyberpunk purple-blue palettes
- oversaturated startup greens
- glossy metallic effects

## Typography

### Font Stack

Current font stack:

- `-apple-system`
- `BlinkMacSystemFont`
- `PingFang SC`
- `Noto Sans SC`
- `Microsoft YaHei`
- `Hiragino Sans GB`
- `sans-serif`

Monospace stack:

- `Menlo`
- `SF Mono`
- `PingFang SC`
- `monospace`

### Type Roles

- Product title: medium-large, bold, compact line height
- English caption: smaller, slightly more spaced out
- Table headers: small and muted
- Numeric cells: monospaced for alignment and scanability
- Secondary context: subtle gray, never heavier than primary data

### Tone

Headings should be concise and informative. Avoid slogan-like copy.

## Logo and Icon Style

### Files

- Main logo mark: `llm_api_pricing_tracker_logo.svg`
- Favicon: `favicon.svg`

### Current Direction

The current brand mark is intentionally minimal. It represents:

- a chart frame
- a few simple value bars
- a downward trend line with light波折

It should communicate price movement quickly, not literal AI symbolism.

### Rules

- Keep the logo icon-only. Do not embed the full product name in the SVG.
- Product text lives in HTML, not inside the brand asset.
- Favor a simple silhouette over complex symbolic storytelling.
- The line should have motion and direction, but not become decorative scribble.
- The icon should remain readable at favicon scale.

### What to Avoid

- brain icons
- dense node networks
- circuit-board metaphors
- dollar signs
- too many disconnected lines
- strong 3D or glossy effects

### Acceptable Evolution

Future logo changes can adjust:

- trend direction emphasis
- line curvature
- color temperature
- frame or axis minimalism

But should preserve:

- simplicity
- small-size clarity
- restrained historical palette

## Controls Style

The controls row should feel utilitarian and compact.

### Search

- left-aligned icon
- small radius
- subtle border
- blue focus ring

### Filter Buttons

- compact pill-like buttons
- neutral by default
- solid blue when active

### Provider Dropdown

- appears as a lightweight utility control
- supports search and batch actions
- should not feel like a heavyweight modal

## Table Style

### Table Role

The pricing table is the primary working surface.

### Visual Rules

- white surface
- subtle border
- thin row separators
- muted header background
- hover highlight only, no heavy row cards
- sortable headers should show state clearly with arrow indicators

### Cell Rules

- provider cell uses a small colored dot and text label
- model cell can include compact tier badges
- numeric cells align right
- numbers use monospace
- unavailable values use subdued gray

### Sorting

The provider column currently defaults to alphabetical sorting by provider name.
Within the same provider, models are secondarily sorted by model name according to
the current table logic.

Any future change to default sorting should also update:

- table header default state
- documentation
- interaction expectations

## Trend Column

### Intent

The trend column provides a quick visual cue before expansion.

### Rules

- If at least two dated points exist, show a mini sparkline.
- If only one effective point exists, show `展开`.
- Clicking the trend cell expands an inline chart row directly below the model row.

### Expanded Chart

The expanded chart should feel like a continuation of the table, not a separate
dashboard card.

Use:

- plain white background
- lightweight line chart
- restrained legends
- compact side info table

Avoid:

- dark chart themes
- oversized chart chrome
- heavy tool panels

### Data Semantics

Trend rendering should use date-normalized series:

- dedupe repeated records from the same day
- merge current-day `pricing.json` values into the chart series
- prefer one effective point per date
- for USD-priced providers, compare raw USD prices and normalize with the current USD/CNY rate so FX drift does not look like vendor price changes
- mini sparkline should summarize only the latest 60 effective points; expanded chart keeps the full normalized series

This rule is part of the design because inconsistent dates create misleading visual
signals.

## Motion and Feedback

Motion should stay minimal.

Allowed:

- subtle hover background changes
- arrow rotation in dropdowns
- lightweight emphasis on clickable trend cells

Avoid:

- bounce effects
- long transitions
- toast-heavy feedback
- animated counters

## Responsive Behavior

On small screens:

- header stacks vertically
- logo remains small and readable
- controls wrap naturally
- table stays horizontally scrollable
- chart panel stacks vertically

The mobile experience should preserve functionality first, decoration second.

## Content and Voice

This product uses utility copy, not marketing copy.

Good examples:

- `输入 /1M`
- `缓存输入 /1M`
- `更新日期`
- `点击展开价格趋势图`

Avoid:

- inspirational headlines
- startup slogans
- decorative feature blurbs

## Implementation Mapping

Current implementation sources:

- layout and UI tokens: `css/style.css`
- document structure: `index.html`
- interactions and chart behavior: `js/app.js`
- logo mark: `llm_api_pricing_tracker_logo.svg`
- favicon: `favicon.svg`

When changing the design, update both the code and this file.

## Future Change Checklist

Before merging any visual change, verify:

1. Does it improve scanning rather than add decoration?
2. Does it preserve the calm data-workbench feel?
3. Is the logo still legible at favicon size?
4. Does the color change remain compatible with mixed Chinese/English typography?
5. Does the trend visualization still reflect data truthfully?
6. Did `docs/design.md` stay aligned with the implementation?
