---
aliases:
  - finance suite
  - ai finance dashboard
  - personal finance tools
status: In progress
ai_summary: "Reflex-based modular finance suite with a persistent AI assistant as the primary interface. Modules (research, notes, options, portfolio) serve as tools and data layers. The assistant synthesizes across modules, remembers user context, and enables natural language interaction with financial data. Uses local LLMs via Ollama plus specialized AI services (sentiment, volatility, embeddings)."
priority: High
start_date: 2024-12-28
end_date:
progress: 10
energy: High
domain:
  - Web
  - AI
  - Finance
stage: Design
iec_score: 8.5
iec_impact: 9
iec_ease: 6
iec_confidence: 9
blocked: false
blocker:
files:
links:
integration_notes: "Three-layer architecture: (1) AI services (LLM, sentiment, volatility, etc.), (2) Modules (research, notes, options, portfolio) as tools/data, (3) Persistent assistant as primary user interface. Modules can be used standalone via UI, but assistant ties everything together."
integration_status: Active development
parent_project:
project_scope: Core project
tool_stack:
  - Reflex
  - Python
  - Ollama
  - DuckDB
  - yfinance
  - Plotly
  - sentence-transformers
  - FinBERT
categories:
  - "[[Projects]]"
  - "[[Finance]]"
  - "[[AI]]"
tags:
  - project
  - finance
  - ai
  - python
  - llm
  - investing
  - agents
DateCreated: Sunday, December 28th 2024
DateLastModified: Monday, December 30th 2024
---

## Overview

Personal finance suite for investment research, structured product analysis, and portfolio management. 

**The core insight:** The modules (research, notes, options, portfolio) are tools and data layers. A **persistent AI assistant** is the primary interface that ties them together. Instead of navigating pages and filling forms, you talk to it.

**What this enables:**
- "What do you think about NVDA this week?" → pulls research, your trade history, synthesizes
- "Analyze this note my banker sent" → parses PDF, runs simulations, explains risks
- "How have my trades been doing?" → queries your log, finds patterns
- Remembers your watchlist, risk tolerance, past conversations

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  FINANCE ASSISTANT                        │  │
│  │         (persistent, conversational, has tools)           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                  │
│         ┌────────────────────┼────────────────────┐            │
│         ▼                    ▼                    ▼            │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │  Research   │     │   Notes     │     │  Options    │  ...  │
│  │   Module    │     │   Module    │     │   Module    │       │
│  │   (tool)    │     │   (tool)    │     │   (tool)    │       │
│  └─────────────┘     └─────────────┘     └─────────────┘       │
│         │                    │                    │            │
│         └────────────────────┼────────────────────┘            │
│                              ▼                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                     AI SERVICES                           │  │
│  │  LLM (Ollama) | Sentiment (FinBERT) | Volatility (GARCH)  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    DATA SERVICES                          │  │
│  │     Market Data (yfinance) | News | Storage (DuckDB)      │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

**Finance Assistant (Interface Layer)**
- Primary way users interact with the suite
- Maintains persistent context (watchlist, preferences, history)
- Routes requests to appropriate modules
- Synthesizes information across modules
- See: [[Finance Suite - Assistant]]

**Modules (Tool/Data Layer)**
- Each module is a self-contained tool the assistant can invoke
- Also accessible via direct UI for power users
- Own their data models and business logic

**AI Services (Intelligence Layer)**
- LLM: Synthesis, explanation, exploration
- Sentiment: FinBERT classification
- Volatility: GARCH forecasting
- Embeddings: Similarity search
- See: [[Finance Suite - AI Services]]

## Modules Overview

### 1. Research Module
**Purpose:** Compress company research for weekly options plays
**Key data:** Quality metrics, configurable range analysis, analyst data, IV/premium levels
**Supports:** Papi's conservative strategy (entry/exit), Tio's aggressive strategy (directional)
**See:** [[Finance Suite - Research Module]]

### 2. Notes Module  
**Purpose:** Decompose structured notes to reveal actual risk/reward
**Key data:** Fee breakdown, risk scenarios, Monte Carlo simulations
**See:** [[Finance Suite - Notes Module]]

### 3. Options Module
**Purpose:** Support weekly options plays with research and tracking
**Key data:** Options chains, payoff diagrams, trade log, performance
**See:** [[Finance Suite - Options Module]]

### 4. Portfolio Module
**Purpose:** Unified view of investment performance
**See:** [[Finance Suite - Portfolio Module]]

## Tech Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | Reflex | Python-native, compiles to React |
| LLM | Ollama (local) | Privacy, no API costs |
| Market Data | yfinance → Polygon | Start free, upgrade later |
| Storage | DuckDB | Embedded, SQL, great for analytics |
| Sentiment | FinBERT | Domain-specific, fast |

### Key Patterns

**Data Provider Adapter:** yfinance breaks often. Abstract behind interface for easy swap.

**LLM Extracts, Python Calculates:** Never ask LLM to do math. LLM extracts variables, Python calculates.

## Goals

### Major Goals
- [ ] Get assistant + research module to "daily driver" state
- [ ] Beat dad/uncle's weekly options returns (visible competition)
- [ ] Have polished demo for job interviews

### Current Action Items
- [x] Document family strategies in detail
- [ ] Set up base Reflex project structure
- [ ] Implement core services (market_data, llm, db)
- [ ] Build research module MVP
- [ ] Create basic assistant with research tools

## Related

- [[Finance Suite - Assistant]]
- [[Finance Suite - AI Services]]
- [[Finance Suite - Research Module]]
- [[Finance Suite - Notes Module]]
- [[Finance Suite - Options Module]]
- [[Finance Suite - Portfolio Module]]

---
Created: 2024-12-28
Updated: 2024-12-30 - Added three-layer architecture, assistant as primary interface
Supersedes: [[Finance Dashboard FD]], [[Structured Note Simulator App]], [[Agent Finance Orchestration]]
