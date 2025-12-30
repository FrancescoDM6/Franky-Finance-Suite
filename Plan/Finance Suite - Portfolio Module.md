---
aliases:
  - portfolio tracker
  - performance dashboard
status: Planned
ai_summary: "Portfolio tracking module for Finance Suite. Unified view of investment performance across all activity - options trades, long positions, and structured notes. Lower priority, to be built after core research and trading modules."
priority: Low
start_date:
end_date:
progress: 0
energy: Low
domain:
  - Web
  - Finance
stage: Planning
iec_score: 5.33
iec_impact: 6
iec_ease: 5
iec_confidence: 5
blocked: true
blocker: "Build research and options modules first"
files:
links:
integration_notes: "Lives in modules/portfolio/. Aggregates data from options trade log and any other tracked positions. May integrate with brokerage API eventually."
integration_status: Planned
parent_project: "[[Finance Suite]]"
project_scope: Feature
tool_stack:
  - Reflex
  - Python
  - DuckDB
  - Plotly
categories:
  - "[[Projects]]"
  - "[[Finance]]"
tags:
  - project
  - finance
  - portfolio
  - python
DateCreated: Saturday, December 28th 2024
DateLastModified: Saturday, December 28th 2024
---

## Overview

Unified view of investment performance. Aggregates data from other modules (options trades, structured note positions) into a single dashboard.

**Build this last.** The other modules need to exist first to have data worth tracking.

## Features (Tentative)

### MVP
- [ ] Manual position entry (for stuff outside the options module)
- [ ] Aggregate view of options trade P&L
- [ ] Basic allocation pie chart
- [ ] Time-series performance chart

### Later
- [ ] Brokerage API integration (read-only, for position import)
- [ ] Benchmark comparison (vs. SPY, QQQ)
- [ ] Tax lot tracking
- [ ] Dividend tracking
- [ ] Structured note position tracking

## Data Sources

- Options module trade log (DuckDB)
- Manual position entries
- Eventually: brokerage API (Schwab, Fidelity, etc.)

## File Structure

```
modules/portfolio/
├── __init__.py
├── page.py
├── state.py
└── components.py
```

## Current Action Items

- [ ] None yet - blocked on other modules

## Related

- [[Finance Suite]] (parent)
- [[Finance Suite - Options Module]] (provides trade data)
- [[Finance Suite - Notes Module]] (provides structured note positions)

---
Created: 2024-12-28
