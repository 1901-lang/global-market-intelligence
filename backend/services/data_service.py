import os
import asyncio
import httpx
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from models.schemas import AssetPrice, MarketContext
from db import get_db

logger = logging.getLogger(__name__)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
NEWS_API_BASE = "https://newsapi.org/v2"
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

# ── Default assets (always present) ──────────────────────────────────────────
_DEFAULT_CRYPTO: Dict[str, Dict] = {
    "BTC": {"id": "bitcoin", "name": "Bitcoin"},
    "ETH": {"id": "ethereum", "name": "Ethereum"},
}

_DEFAULT_COMMODITY: Dict[str, Dict] = {
    "GOLD": {"ticker": "GC=F", "name": "Gold"},
    "OIL":  {"ticker": "CL=F", "name": "Crude Oil"},
}

# ── Runtime-configurable assets (merged with defaults) ───────────────────────
# These are populated from the `configured_assets` DB table at startup and
# refreshed whenever an admin adds / removes an asset via the API.
_runtime_crypto: Dict[str, Dict] = {}
_runtime_commodity: Dict[str, Dict] = {}

# Keep the old names as aliases for backwards compatibility with any direct imports
CRYPTO_ASSETS = _DEFAULT_CRYPTO
COMMODITY_SYMBOLS = _DEFAULT_COMMODITY

MACRO_SYMBOLS = {
    "USD_INDEX": "DX-Y.NYB",
    "BOND_10Y": "^TNX",
    "VIX": "^VIX",
}

_cache: Dict[str, Any] = {}
_cache_ttl: Dict[str, float] = {}
CACHE_SECONDS = 55


def _is_cached(key: str) -> bool:
    import time
    return key in _cache and (time.time() - _cache_ttl.get(key, 0)) < CACHE_SECONDS


def _set_cache(key: str, value: Any):
    import time
    _cache[key] = value
    _cache_ttl[key] = time.time()


def get_active_crypto_assets() -> Dict[str, Dict]:
    """Return the current merged crypto asset map (defaults + admin-added)."""
    merged = dict(_DEFAULT_CRYPTO)
    merged.update(_runtime_crypto)
    return merged


def get_active_commodity_assets() -> Dict[str, Dict]:
    """Return the current merged commodity asset map (defaults + admin-added)."""
    merged = dict(_DEFAULT_COMMODITY)
    merged.update(_runtime_commodity)
    return merged


async def load_configured_assets():
    """Reload the runtime asset lists from the `configured_assets` DB table.

    This is called at startup (from main.py) and after any admin asset change.
    Thread-safe because Python dict assignment is atomic on CPython.
    """
    global _runtime_crypto, _runtime_commodity
    new_crypto: Dict[str, Dict] = {}
    new_commodity: Dict[str, Dict] = {}
    try:
        async with get_db() as db:
            rows = await db.fetchall(
                "SELECT symbol, name, asset_type, source_id FROM configured_assets WHERE is_active = 1"
            )
        for row in rows:
            sym = row["symbol"].upper()
            if row["asset_type"] == "crypto":
                new_crypto[sym] = {"id": row["source_id"], "name": row["name"]}
            elif row["asset_type"] == "commodity":
                new_commodity[sym] = {"ticker": row["source_id"], "name": row["name"]}
    except Exception as exc:
        logger.warning("load_configured_assets failed: %s", exc)
        return

    # Remove default assets to avoid duplication — they are always merged in at call time
    for sym in _DEFAULT_CRYPTO:
        new_crypto.pop(sym, None)
    for sym in _DEFAULT_COMMODITY:
        new_commodity.pop(sym, None)

    _runtime_crypto = new_crypto
    _runtime_commodity = new_commodity
    logger.info(
        "Asset config reloaded: %d extra crypto, %d extra commodity (defaults: %d crypto, %d commodity)",
        len(new_crypto),
        len(new_commodity),
        len(_DEFAULT_CRYPTO),
        len(_DEFAULT_COMMODITY),
    )


async def fetch_crypto_prices() -> List[AssetPrice]:
    cache_key = "crypto_prices"
    if _is_cached(cache_key):
        return _cache[cache_key]

    active_crypto = get_active_crypto_assets()
    ids = ",".join(info["id"] for info in active_crypto.values())
    url = (
        f"{COINGECKO_BASE}/coins/markets"
        f"?vs_currency=usd&ids={ids}"
        f"&price_change_percentage=1h,24h"
    )
    results: List[AssetPrice] = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        symbol_map = {info["id"]: sym for sym, info in active_crypto.items()}
        for coin in data:
            sym = symbol_map.get(coin["id"], coin["symbol"].upper())
            results.append(
                AssetPrice(
                    symbol=sym,
                    name=coin["name"],
                    price=coin["current_price"] or 0.0,
                    change_1h=coin.get("price_change_percentage_1h_in_currency") or 0.0,
                    change_24h=coin.get("price_change_percentage_24h") or 0.0,
                    volume_24h=coin.get("total_volume") or 0.0,
                    market_cap=coin.get("market_cap") or 0.0,
                    asset_type="crypto",
                    timestamp=datetime.now(timezone.utc),
                )
            )
    except Exception as exc:
        logger.warning(f"CoinGecko fetch failed: {exc}. Using mock data.")
        results = _mock_crypto()
    _set_cache(cache_key, results)
    return results


def _mock_crypto() -> List[AssetPrice]:
    return [
        AssetPrice(
            symbol="BTC", name="Bitcoin", price=68500.0,
            change_1h=0.3, change_24h=1.8, volume_24h=28e9, market_cap=1.35e12,
            asset_type="crypto", timestamp=datetime.now(timezone.utc),
        ),
        AssetPrice(
            symbol="ETH", name="Ethereum", price=3450.0,
            change_1h=-0.1, change_24h=0.9, volume_24h=15e9, market_cap=4.1e11,
            asset_type="crypto", timestamp=datetime.now(timezone.utc),
        ),
    ]


async def fetch_commodity_prices() -> List[AssetPrice]:
    cache_key = "commodity_prices"
    if _is_cached(cache_key):
        return _cache[cache_key]

    active_commodities = get_active_commodity_assets()
    results: List[AssetPrice] = []
    try:
        import yfinance as yf
        tickers = [info["ticker"] for info in active_commodities.values()]
        data = yf.download(tickers, period="2d", interval="1d", progress=False, auto_adjust=True)
        for sym, info in active_commodities.items():
            ticker = info["ticker"]
            try:
                closes = data["Close"][ticker].dropna()
                if len(closes) >= 2:
                    price = float(closes.iloc[-1])
                    prev = float(closes.iloc[-2])
                    change = ((price - prev) / prev * 100) if prev else 0.0
                elif len(closes) == 1:
                    price = float(closes.iloc[-1])
                    change = 0.0
                else:
                    raise ValueError("No data")
                results.append(
                    AssetPrice(
                        symbol=sym,
                        name=info["name"],
                        price=price,
                        change_1h=0.0,
                        change_24h=change,
                        volume_24h=0.0,
                        market_cap=0.0,
                        asset_type="commodity",
                        timestamp=datetime.now(timezone.utc),
                    )
                )
            except Exception:
                results.append(_mock_commodity(sym, info["name"]))
    except Exception as exc:
        logger.warning(f"yfinance commodity fetch failed: {exc}. Using mock data.")
        results = [_mock_commodity(s, i["name"]) for s, i in active_commodities.items()]
    _set_cache(cache_key, results)
    return results


def _mock_commodity(sym: str, name: str) -> AssetPrice:
    defaults = {"GOLD": 2350.0, "OIL": 82.5}
    return AssetPrice(
        symbol=sym, name=name, price=defaults.get(sym, 100.0),
        change_1h=0.0, change_24h=0.5, volume_24h=0.0, market_cap=0.0,
        asset_type="commodity", timestamp=datetime.now(timezone.utc),
    )


async def fetch_macro_context() -> MarketContext:
    cache_key = "macro_context"
    if _is_cached(cache_key):
        return _cache[cache_key]

    usd_index = None
    bond_yield = None
    vix = None
    try:
        import yfinance as yf
        tickers = list(MACRO_SYMBOLS.values())
        data = yf.download(tickers, period="2d", interval="1d", progress=False, auto_adjust=True)
        closes = data["Close"] if "Close" in data else data

        def _last_val(ticker: str) -> Optional[float]:
            try:
                series = closes[ticker].dropna()
                return float(series.iloc[-1]) if len(series) > 0 else None
            except Exception:
                return None

        usd_index = _last_val(MACRO_SYMBOLS["USD_INDEX"])
        bond_yield = _last_val(MACRO_SYMBOLS["BOND_10Y"])
        vix = _last_val(MACRO_SYMBOLS["VIX"])
    except Exception as exc:
        logger.warning(f"yfinance macro fetch failed: {exc}. Using defaults.")
        usd_index = 104.5
        bond_yield = 4.35
        vix = 16.2

    news_sentiment = await fetch_news_sentiment()
    ctx = MarketContext(
        usd_index=usd_index,
        bond_yield_10y=bond_yield,
        vix=vix,
        news_sentiment=news_sentiment,
        on_chain_activity=0.62,
        timestamp=datetime.now(timezone.utc),
    )
    _set_cache(cache_key, ctx)
    return ctx


async def fetch_news_sentiment() -> float:
    if not NEWS_API_KEY:
        return 0.05

    cache_key = "news_sentiment"
    if _is_cached(cache_key):
        return _cache[cache_key]

    keywords = "bitcoin OR gold OR oil OR crypto OR market OR inflation"
    url = (
        f"{NEWS_API_BASE}/everything?q={keywords}"
        f"&language=en&pageSize=20&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        articles = data.get("articles", [])
        sentiment = _naive_sentiment(articles)
    except Exception as exc:
        logger.warning(f"NewsAPI fetch failed: {exc}. Defaulting sentiment to 0.")
        sentiment = 0.0

    _set_cache(cache_key, sentiment)
    return sentiment


POSITIVE_WORDS = {
    "surge", "rally", "gain", "rise", "bull", "bullish", "record", "high", "growth",
    "positive", "strong", "up", "increase", "profit", "boom", "recovery", "breakthrough",
}
NEGATIVE_WORDS = {
    "crash", "drop", "fall", "bear", "bearish", "decline", "loss", "recession", "risk",
    "fear", "down", "decrease", "sell", "concern", "worry", "crisis", "weak", "warning",
}


def _naive_sentiment(articles: List[Dict]) -> float:
    score = 0
    count = 0
    for article in articles:
        text = ((article.get("title") or "") + " " + (article.get("description") or "")).lower()
        words = text.split()
        for w in words:
            if w in POSITIVE_WORDS:
                score += 1
                count += 1
            elif w in NEGATIVE_WORDS:
                score -= 1
                count += 1
    if count == 0:
        return 0.0
    return max(-1.0, min(1.0, score / max(count, 1)))


async def fetch_all_assets() -> List[AssetPrice]:
    crypto, commodities = await asyncio.gather(
        fetch_crypto_prices(), fetch_commodity_prices()
    )
    return crypto + commodities
