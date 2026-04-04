// ── Landing page content configuration ──────────────────────────────────────
// All structured content is centralised here so the landing page is easy
// to update without touching component logic.

export const NAV_LINKS = [
  { label: 'Platform', href: '#capabilities' },
  { label: 'Methodology', href: '#methodology' },
  { label: 'Global Markets', href: '#global-market' },
] as const

export interface TickerItem {
  symbol: string
  label: string
  price: string
  change: string
  positive: boolean
}

export const TICKER_ITEMS: TickerItem[] = [
  { symbol: 'BTC/USD', label: 'Bitcoin', price: '64,230', change: '+2.4%', positive: true },
  { symbol: 'ETH/USD', label: 'Ethereum', price: '3,450', change: '-0.8%', positive: false },
  { symbol: 'XAU/USD', label: 'Gold', price: '2,348', change: '+0.5%', positive: true },
  { symbol: 'US02Y', label: '2Y Treasury', price: '4.82%', change: '+1.2bps', positive: false },
  { symbol: 'DXY', label: 'Dollar Index', price: '104.50', change: '-0.2%', positive: false },
  { symbol: 'SPX', label: 'S&P 500', price: '5,204', change: '+0.7%', positive: true },
  { symbol: 'WTI', label: 'Crude Oil', price: '82.10', change: '-1.1%', positive: false },
  { symbol: 'VIX', label: 'Volatility', price: '14.32', change: '-3.5%', positive: false },
]

export interface InfrastructureItem {
  label: string
  description: string
  icon: string
}

export const INFRASTRUCTURE_ITEMS: InfrastructureItem[] = [
  { label: 'Alternative Datasets', description: 'On-chain, satellite, sentiment feeds', icon: '⬡' },
  { label: 'Quantitative Tools', description: 'Regime detection, factor analysis', icon: '◈' },
  { label: 'Data Orchestration', description: 'Normalised multi-source pipeline', icon: '⟁' },
  { label: 'API Feeds & Export', description: 'Structured JSON, webhook, CSV export', icon: '⊞' },
  { label: 'Data Provenance', description: 'Full audit trail per signal output', icon: '◉' },
]

export interface CapabilityCard {
  icon: string
  title: string
  description: string
  tag: string
}

export const CAPABILITY_CARDS: CapabilityCard[] = [
  {
    icon: '⬡',
    title: 'Research Orchestration Agent',
    description: 'Coordinates multi-step research workflows, schedules agent runs, and synthesises cross-asset intelligence into structured briefings.',
    tag: 'Core Agent',
  },
  {
    icon: '◈',
    title: 'Regime Analytics Engine',
    description: 'Detects macro regime transitions — risk-on, risk-off, stagflation, reflation — and surfaces actionable regime labels per asset class.',
    tag: 'Analytics',
  },
  {
    icon: '⟁',
    title: 'Longitudinal Thesis State Engine',
    description: 'Tracks the lifecycle of investment theses over time, records evidence accumulation, flags invalidation conditions, and maintains thesis continuity.',
    tag: 'State Engine',
  },
  {
    icon: '⊕',
    title: 'Catalyst Structuring Layer',
    description: 'Classifies and ranks market catalysts by magnitude, directionality, and timeframe. Links catalysts to affected assets with confidence scores.',
    tag: 'Structuring',
  },
  {
    icon: '⊗',
    title: 'Multi-Model Debate Engine',
    description: 'Runs consensus scoring across multiple AI models, surfaces dissenting views, and produces weighted final signals with model attribution.',
    tag: 'Consensus',
  },
  {
    icon: '◉',
    title: 'Explainable Driver Framework',
    description: 'Every output includes structured evidence chains, confidence levels, contradictions, and audit-ready provenance for institutional review.',
    tag: 'Explainability',
  },
]

export interface MethodologyStep {
  step: number
  label: string
  title: string
  description: string
  detail: string
}

export const METHODOLOGY_STEPS: MethodologyStep[] = [
  {
    step: 1,
    label: 'SENSE',
    title: 'Ingest & Normalise',
    description: 'Live market context ingested from price feeds, macro data, on-chain metrics, and alternative datasets.',
    detail: 'Multi-source normalisation pipeline',
  },
  {
    step: 2,
    label: 'JUDGE',
    title: 'Model Debate Loop',
    description: 'Three independent AI models generate initial signals, then engage in a structured debate loop to surface disagreements.',
    detail: 'OpenAI · Anthropic · Gemini',
  },
  {
    step: 3,
    label: 'REACT',
    title: 'Consensus & Alerts',
    description: 'Weighted consensus scoring produces final signals. High-confidence changes trigger structured alerts with severity classification.',
    detail: 'Confidence-weighted consensus',
  },
  {
    step: 4,
    label: 'EXPLAIN',
    title: 'Structured Outputs',
    description: 'Every signal is accompanied by a driver narrative, evidence list, confidence band, dissenting model views, and invalidation conditions.',
    detail: 'Auditable reasoning chains',
  },
  {
    step: 5,
    label: 'LEARN',
    title: 'Outcome Tracking',
    description: 'Prediction outcomes are recorded, model weights are updated based on accuracy, and signal quality improves over time.',
    detail: 'Adaptive model weighting',
  },
]

export interface ExplainabilityTab {
  id: string
  label: string
  heading: string
  description: string
  features: string[]
}

export const EXPLAINABILITY_TABS: ExplainabilityTab[] = [
  {
    id: 'datasets',
    label: 'High-Fidelity Datasets',
    heading: 'Institutional-grade data infrastructure',
    description: 'Every signal traces back to verified source data with normalisation logs, staleness indicators, and source quality scores.',
    features: [
      'Real-time price feeds across crypto and commodities',
      'Macro context: DXY, 10Y yield, VIX, news sentiment',
      'On-chain activity indicators (normalised 0–1)',
      'Configurable asset universe via admin API',
    ],
  },
  {
    id: 'tools',
    label: 'Advanced Analyst Tools',
    heading: 'Quantitative tooling for research workflows',
    description: 'Analysts get structured access to correlation matrices, price history, performance attribution, and model weight inspection.',
    features: [
      'Pairwise Pearson correlation matrix (configurable window)',
      'Price history per asset (up to 100 data points)',
      'Model accuracy and adaptive weight tracking',
      'AI-generated market narrative reports (pre-market / close)',
    ],
  },
  {
    id: 'provenance',
    label: 'Data Provenance',
    heading: 'Full audit trail from signal to source',
    description: 'Every intelligence output is traceable. Model reasoning, dissenting views, and evidence chains are stored and queryable.',
    features: [
      'Per-model reasoning arrays stored in database',
      'Dissenting model identification per consensus result',
      'Timestamped prediction records for outcome evaluation',
      'Agent activity logs for full operational audit',
    ],
  },
]

export interface TargetUser {
  role: string
  description: string
  useCase: string
  icon: string
}

export const TARGET_USERS: TargetUser[] = [
  {
    icon: '◈',
    role: 'Discretionary Macro Traders',
    description: 'Build and track structured theses across rates, FX, commodities, and crypto with AI-assisted research continuity.',
    useCase: 'Thesis tracking, regime-aware signals',
  },
  {
    icon: '⬡',
    role: 'Institutional Strategy Teams',
    description: 'Generate structured intelligence briefings, monitor cross-asset consensus, and surface actionable research at scale.',
    useCase: 'Daily briefings, consensus monitoring',
  },
  {
    icon: '◉',
    role: 'Crypto Research Desks',
    description: 'Track on-chain activity, sentiment, and cross-asset correlation to produce auditable research outputs for institutional clients.',
    useCase: 'On-chain analytics, narrative generation',
  },
  {
    icon: '⟁',
    role: 'Family Offices',
    description: 'Access institutional-grade market intelligence without building a full research infrastructure. Decision support with explainable outputs.',
    useCase: 'Portfolio decision support',
  },
  {
    icon: '⊕',
    role: 'Systematic Portfolio Managers',
    description: 'Feed structured signals into allocation models. Model performance tracking and adaptive weighting support systematic workflows.',
    useCase: 'Signal feeds, model performance data',
  },
  {
    icon: '⊞',
    role: 'Corporate Intelligence Leads',
    description: 'Monitor macro regimes and commodity market conditions relevant to operational planning, procurement, and risk hedging.',
    useCase: 'Macro monitoring, commodity intelligence',
  },
]

export interface MarketNode {
  city: string
  market: string
  index: string
  change: string
  volume: string
  regime: string
  models: number
  positive: boolean
  position: { top: string; left: string }
}

export const MARKET_NODES: MarketNode[] = [
  {
    city: 'New York',
    market: 'US Equities / Credit',
    index: 'SPX 5,204',
    change: '+0.7%',
    volume: '$487B',
    regime: 'Risk-On',
    models: 3,
    positive: true,
    position: { top: '35%', left: '22%' },
  },
  {
    city: 'London',
    market: 'FTSE / Gilts / FX',
    index: 'FTSE 7,892',
    change: '-0.3%',
    volume: '$182B',
    regime: 'Transitional',
    models: 3,
    positive: false,
    position: { top: '22%', left: '45%' },
  },
  {
    city: 'Frankfurt',
    market: 'Bund / DAX',
    index: 'DAX 18,104',
    change: '+0.4%',
    volume: '$94B',
    regime: 'Risk-On',
    models: 2,
    positive: true,
    position: { top: '25%', left: '49%' },
  },
  {
    city: 'Tokyo',
    market: 'JGBs / Nikkei / JPY',
    index: 'NKY 38,560',
    change: '+1.1%',
    volume: '$198B',
    regime: 'Reflationary',
    models: 3,
    positive: true,
    position: { top: '30%', left: '78%' },
  },
  {
    city: 'Hong Kong',
    market: 'Hang Seng / CNH',
    index: 'HSI 17,220',
    change: '-0.9%',
    volume: '$87B',
    regime: 'Risk-Off',
    models: 2,
    positive: false,
    position: { top: '40%', left: '74%' },
  },
]
