# Institutional Market Intelligence

A free-first, EOD-focused Indian and global market research workspace.

## Product principles
- No custom backend or paid market-data API dependency.
- Browser-side processing with local persistence in IndexedDB.
- CSV/XLSX import is a first-class fallback when a source blocks browser access or requires authentication.
- Every observation must retain its source, market date, retrieval time, and data-quality status.
- Missing, stale, or unavailable data must be explicit. Never fabricate prices, signals, broker recommendations, or company guidance.
- This repository is independent of the existing Algo-trading project.

## Architecture
- `src/app`: application shell.
- `src/core`: shared domain types and data-quality rules.
- `src/data`: source registry, import contracts, and persistence.
- `src/modules`: isolated research modules.
- `src/components`: reusable UI components.
- `src/styles`: design tokens and responsive styling.

## Development
```bash
npm install
npm run dev
npm run typecheck
npm run build
```

## Data safety
The foundation has no live market feed. Data connectors will be enabled only after source access, licensing, and browser restrictions are reviewed.

## Delivery plan
1. Foundation and app shell
2. Source registry, validation, IndexedDB, CSV import
3. EOD cash-market data
4. F&O and options intelligence
5. Sector, delivery, and institutional activity
6. Broker research and company intelligence
7. Commodities and supply chain
8. Opportunity scoring and historical evaluation
