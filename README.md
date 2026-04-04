Global Market Intelligence Platform

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

## 🤖 AI Agent Team

Five specialized agents run inside the backend, each with its own scheduled workflow and
dedicated API endpoints. All agents use `gpt-5.4` via `OPENAI_API_KEY` and degrade
gracefully when no key is present.

| # | Agent | Role | Schedule |
|---|-------|------|----------|
| 1 | **Orchestrator** (COO) | Admin briefings, agent health, operational Q&A | Daily @ 09:00 |
| 2 | **Marketing Director** | Market-tied social posts, lead nurture emails | Daily @ 08:30, every 2 h |
| 3 | **Chief Analyst** | Narrative pre-market & close reports, asset deep-dives | Daily @ 07:00 & 16:30 |
| 4 | **Customer Success** | Session-based support chat, user onboarding | Daily @ 10:00 |
| 5 | **Analytics** | KPI reports, cross-agent activity log, anomaly detection | Daily @ 08:00, every 4 h |

### Agent API Endpoints

```
GET  /api/agents/status                          # all 5 agent statuses
GET  /api/agents/activity                        # cross-agent activity log

# Orchestrator
GET  /api/agents/orchestrator/briefing           # latest admin briefing
POST /api/agents/orchestrator/briefing/generate  # trigger on-demand
POST /api/agents/orchestrator/query              # {"query": "..."}

# Marketing
GET  /api/agents/marketing/content               # recent content items
POST /api/agents/marketing/generate              # trigger teaser + nurture email
POST /api/agents/marketing/lead-insight          # {"lead_context": "..."}

# Market Intelligence
GET  /api/agents/market-intel/narrative          # latest narrative report
POST /api/agents/market-intel/narrative/generate # trigger on-demand
POST /api/agents/market-intel/deep-dive          # {"symbol": "BTC"}

# Customer Success
POST /api/agents/support/chat                    # {"session_id": "...", "message": "..."}
GET  /api/agents/support/chat/{session_id}       # chat history
POST /api/agents/support/onboard                 # {"name":"...", "interest":"...", "experience":"..."}

# Analytics
GET  /api/agents/analytics/kpi                   # latest KPI report
POST /api/agents/analytics/kpi/generate          # trigger on-demand
POST /api/agents/analytics/anomaly-check         # {"metrics": {...}}
```

The agent panel is embedded directly in the dashboard UI under the Model Performance table.

---

## 🚀 Deployment

### Hostinger VPS — auren-workspace.com

The production stack runs on a Hostinger VPS with Docker Compose, nginx reverse proxy, and Let's Encrypt TLS. Services are mapped as follows:

| URL | Service |
|-----|---------|
| `https://auren-workspace.com` | Next.js frontend |
| `https://www.auren-workspace.com` | → redirect to apex |
| `https://api.auren-workspace.com` | FastAPI backend |

#### DNS records (configure in Hostinger DNS panel)

| Type | Name | Value |
|------|------|-------|
| A | `@` | `<your-vps-ip>` |
| A | `www` | `<your-vps-ip>` |
| A | `api` | `<your-vps-ip>` |

#### Step-by-step deployment

**1. SSH into the VPS and install Docker**
```bash
apt-get update && apt-get install -y docker.io docker-compose-plugin
```

**2. Clone the repository**
```bash
git clone https://github.com/1901-lang/global-market-intelligence.git
cd global-market-intelligence
```

**3. Create the production environment file**
```bash
cp .env.example .env
```
Edit `.env` and fill in all required secrets, then set:
```ini
ALLOWED_ORIGINS=https://auren-workspace.com,https://www.auren-workspace.com
NEXT_PUBLIC_API_URL=https://api.auren-workspace.com
SMTP_FROM=alerts@auren-workspace.com
```

**4. Issue TLS certificates (once)**

Start a temporary HTTP-only nginx so Certbot can complete the ACME challenge:
```bash
# Bring up everything except nginx first
docker compose -f docker-compose.prod.yml up -d db backend frontend certbot

# Run certbot to obtain the certificates
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d auren-workspace.com -d www.auren-workspace.com -d api.auren-workspace.com \
  --email admin@auren-workspace.com --agree-tos --no-eff-email
```

**5. Start the full stack (including nginx)**
```bash
docker compose -f docker-compose.prod.yml up -d
```

Verify all containers are healthy:
```bash
docker compose -f docker-compose.prod.yml ps
```

**6. Certificate renewal**

Certbot runs inside its container and renews certificates automatically every 12 hours. Nginx picks up renewed certificates on the next reload.

To force an immediate renewal check:
```bash
docker compose -f docker-compose.prod.yml exec certbot certbot renew --quiet
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

---

### Other hosting options

- **Frontend** → Vercel (`npm run build` → deploy). Set `NEXT_PUBLIC_API_URL` as an
  environment variable pointing to `https://api.auren-workspace.com`.
- **Backend** → Railway / Render (`uvicorn main:app --host 0.0.0.0 --port 8000`).
  The backend must run as a **persistent process** — APScheduler requires a long-lived
  instance and will not work correctly on serverless platforms (e.g. AWS Lambda, Vercel
  serverless functions). Use a container or VM-based deployment.

