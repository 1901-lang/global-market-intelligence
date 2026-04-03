# Market Research Analyst Agent

Agent 6 of the AIP platform. Produces institutional-grade, structured research artifacts for professional users: discretionary macro traders, crypto macro traders, family offices, and research analysts.

## Overview

The Research Analyst agent combines deterministic macro regime classification with LLM-driven research note generation to deliver thesis-driven, structured market analysis. All outputs are persisted to the database and exposed via REST API.

## Architecture

```
regime_classifier.py  ←  MarketContext (DXY, VIX, 10Y yield, sentiment)
        ↓
agents/research.py    ←  LLM (llm_chat) + DB persistence
        ↓
REST API endpoints    ←  FastAPI (main.py)
        ↓
ResearchPanel.tsx     ←  Next.js frontend component
```

## Components

### `backend/services/regime_classifier.py`

Deterministic rule-based classifier. No LLM required. Reads `MarketContext` fields and applies prioritised signal rules to return a `MarketRegime`:

| Label | Trigger conditions |
|---|---|
| `volatility_stress` | VIX ≥ 25 |
| `inflationary` | DXY strong + 10Y yield high |
| `risk_on` | DXY weak + positive sentiment, or VIX calm + positive sentiment |
| `risk_off` | DXY strong + negative sentiment, or negative sentiment (fallback) |
| `liquidity_supportive` | DXY weak + 10Y yield low |
| `dollar_strength` | DXY ≥ 104 |
| `dollar_weakness` | DXY ≤ 100 |
| `inflationary` | 10Y yield ≥ 4.5% (standalone) |
| `disinflationary` | 10Y yield ≤ 3.5% (standalone) |
| `mixed_transition` | Conflicting or insufficient signals |

**Thresholds** (tunable constants at top of file):
- `VIX_STRESS = 25.0`, `VIX_LOW = 15.0`
- `DXY_STRONG = 104.0`, `DXY_WEAK = 100.0`
- `YIELD_HIGH = 4.5`, `YIELD_LOW = 3.5`
- `SENTIMENT_POSITIVE = 0.1`, `SENTIMENT_NEGATIVE = -0.1`

### `backend/agents/research.py`

Main agent module. Responsibilities:

- **`generate_daily_note(state)`** — Platform-wide daily research note. Calls regime classifier, then LLM for structured JSON. Falls back to deterministic note if no LLM key.
- **`generate_deep_research(asset_symbol, state)`** — Asset-specific deep research note with price data, model consensus, and macro context.
- **`generate_thesis_change(asset_symbol, state)`** — Compares two most recent notes for an asset; LLM produces a `ThesisChange` summary.
- **`generate_catalyst_memo(state)`** — Identifies 3–5 key catalyst events from current market state.
- **`run_premarket_note(state)`** — Scheduled wrapper for 07:30 pre-market note.
- **`run_eod_wrap(state)`** — Scheduled wrapper for 17:00 end-of-day wrap note.

All notes fall back gracefully when no LLM API key is configured.

## Database Tables

| Table | Purpose |
|---|---|
| `research_notes` | All research notes (daily, deep-dive, intraday) |
| `thesis_history` | Thesis change records |
| `catalyst_events` | Identified market catalyst events |
| `market_regimes` | Historical regime classifications |

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/agents/research/status` | No | Agent status + last run |
| GET | `/api/agents/research/latest` | No | Latest note (optional `?asset=BTC`) |
| GET | `/api/agents/research/notes` | No | Paginated history (`?limit=20&asset=BTC`) |
| POST | `/api/agents/research/generate` | Yes | On-demand platform-wide note |
| POST | `/api/agents/research/deep-dive` | Yes | Asset-specific deep research (`{"symbol": "BTC"}`) |
| POST | `/api/agents/research/thesis-change` | Yes | Thesis change analysis (`{"symbol": "BTC"}`) |
| GET | `/api/agents/research/catalysts` | No | Catalyst events (`?limit=20&status=pending`) |
| POST | `/api/agents/research/catalysts/generate` | Yes | On-demand catalyst memo |
| GET | `/api/agents/research/regime` | No | Latest regime classification |

## Scheduled Jobs

| Job ID | Schedule | Function |
|---|---|---|
| `research_premarket` | Daily 07:30 | `run_premarket_note` |
| `research_eod_wrap` | Daily 17:00 | `run_eod_wrap` |

## Research Note Structure

```json
{
  "asset": "PLATFORM",
  "note_type": "daily_note",
  "time_horizon": "1-3d",
  "market_regime": "risk_on",
  "thesis": "Directional view in one sentence",
  "confidence": 0.72,
  "key_drivers": ["...", "..."],
  "confirming_evidence": ["..."],
  "contradictory_evidence": ["..."],
  "key_risks": ["..."],
  "catalysts": ["..."],
  "invalidation_conditions": ["..."],
  "scenario_analysis": [
    {"label": "bull", "probability": 0.3, "thesis": "...", "price_target": null},
    {"label": "base", "probability": 0.5, "thesis": "...", "price_target": null},
    {"label": "bear", "probability": 0.2, "thesis": "...", "price_target": null}
  ],
  "summary": "2-3 sentence executive summary"
}
```

## Frontend Component

`frontend/app/components/ResearchPanel.tsx` — Terminal-style panel with three tabs:

- **📋 Research Note** — Latest note with thesis, confidence, drivers, risks, evidence, invalidation conditions, scenario analysis, and an asset deep-dive input
- **🌐 Regime** — Current regime badge with rationale and contributing factors
- **⚡ Catalysts** — Catalyst watch list with importance, event type, and asset scope tags

Auto-refreshes every 60 seconds.

## Fallback Behaviour

When `OPENAI_API_KEY` is not set, the agent produces deterministic fallback notes from live asset prices and AI consensus signals. The notes indicate that full research requires an API key. Regime classification always works without an API key (rule-based only).

## Disclaimer

All research outputs are for informational and decision-support purposes only. Not financial advice.
