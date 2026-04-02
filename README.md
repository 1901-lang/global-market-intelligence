# AIP — Agentic Multi-Model Market Intelligence Platform

A production-ready full-stack decision-support intelligence platform that tracks real-time prices of commodities (Gold, Oil) and digital assets (BTC, ETH), runs them through multiple AI models (OpenAI, Claude, Gemini) via a debate loop, and surfaces BUY/SELL/HOLD consensus signals with confidence scores, live alerts, and daily AI-generated briefs.

> **⚠️ This is NOT automated trading. It is a decision-support intelligence platform.**

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+

### 1. Clone & configure

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
# Backend runs on http://localhost:8000
```

### 3. Frontend

```bash
cd frontend
cp ../.env.example .env.local
# Edit NEXT_PUBLIC_API_URL if needed
npm install
npm run dev
# Frontend runs on http://localhost:3000
```

---

## 📁 Project Structure

```
/backend
  main.py              # FastAPI app + update scheduler
  database.py          # SQLite schema + init
  models/
    schemas.py         # Pydantic models
  services/
    data_service.py    # CoinGecko, Yahoo Finance, NewsAPI
    signal_engine.py   # Rule-based signal detection
    model_wrapper.py   # OpenAI / Claude / Gemini wrappers
    consensus_engine.py # Weighted voting + debate loop
    learning_engine.py  # Adaptive model performance tracking
    alert_engine.py    # Alert triggering + storage
    brief_generator.py # Daily AI-generated market brief

/frontend
  app/
    page.tsx           # Main dashboard
    layout.tsx         # Root layout
    globals.css        # Global styles
    components/
      AssetCard.tsx    # Price + signal card
      SignalBadge.tsx  # BUY/SELL/HOLD badge
      AlertFeed.tsx    # Live alerts panel
      AnalyticsPanel.tsx # Price charts (Recharts)
      ConsensusView.tsx  # Multi-model debate view
      BriefPanel.tsx   # Daily brief display
```

---

## 🔑 Environment Variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic (Claude) API key |
| `GEMINI_API_KEY` | Google Gemini API key |
| `NEWS_API_KEY` | NewsAPI.org key for sentiment |
| `DB_PATH` | SQLite DB path (default: `aip.db`) |
| `NEXT_PUBLIC_API_URL` | Backend URL for frontend |

> **Note:** The platform works without API keys using deterministic fallback logic (HOLD signals, mock prices). Add real API keys to enable live AI analysis.

---

## ⚙️ Architecture

1. **Data Service** — fetches live prices every 60s from CoinGecko (crypto) and Yahoo Finance (commodities/macro)
2. **Signal Engine** — rule-based signals from price momentum, USD, yields, sentiment, VIX
3. **Model Wrapper** — async parallel calls to OpenAI, Claude, Gemini
4. **Debate Loop** — each model sees the others' reasoning and can revise its output
5. **Consensus Engine** — weighted voting with performance-adjusted model weights
6. **Learning Engine** — tracks prediction accuracy per model per asset, adjusts weights
7. **Alert Engine** — fires alerts on signal changes and high-confidence readings
8. **Brief Generator** — daily narrative summary via OpenAI

---

## 🚀 Deployment

- **Frontend** → Vercel (`npm run build` → deploy)
- **Backend** → Railway / Render (`uvicorn main:app --host 0.0.0.0 --port 8000`)

Set `NEXT_PUBLIC_API_URL` to your deployed backend URL on Vercel.

