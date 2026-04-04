import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from db import get_db
from models.schemas import ModelPerformance, ConsensusResult

logger = logging.getLogger(__name__)

MODEL_NAMES = ["openai", "claude", "gemini"]
DEFAULT_WEIGHT = 1.0
MIN_WEIGHT = 0.2
MAX_WEIGHT = 2.0

# Minimum absolute price change (%) to classify a BUY/SELL as directionally correct
_CORRECT_THRESHOLD_PCT = 0.05


async def get_model_weights(asset: str) -> Dict[str, float]:
    weights: Dict[str, float] = {}
    try:
        async with get_db() as db:
            rows = await db.fetchall(
                "SELECT model_name, weight FROM model_performance WHERE asset = ?",
                (asset,),
            )
        for row in rows:
            weights[row["model_name"]] = row["weight"]
    except Exception as exc:
        logger.warning(f"Failed to load model weights: {exc}")
    # Fill defaults
    for m in MODEL_NAMES:
        weights.setdefault(m, DEFAULT_WEIGHT)
    return weights


async def record_prediction(asset: str, model_name: str):
    try:
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO model_performance (model_name, asset, total_predictions, correct_predictions, accuracy, weight, last_updated)
                VALUES (?, ?, 1, 0, 0.0, 1.0, ?)
                ON CONFLICT(model_name, asset) DO UPDATE SET
                    total_predictions = total_predictions + 1,
                    last_updated = ?
                """,
                (model_name, asset, datetime.now(timezone.utc), datetime.now(timezone.utc)),
            )
            await db.commit()
    except Exception as exc:
        logger.warning(f"record_prediction failed: {exc}")


async def record_outcome(
    asset: str,
    model_name: str,
    was_correct: bool,
):
    """
    Call after a prediction can be evaluated (e.g., 1h later).
    Adjusts weight based on accuracy.
    """
    try:
        async with get_db() as db:
            row = await db.fetchone(
                "SELECT * FROM model_performance WHERE model_name = ? AND asset = ?",
                (model_name, asset),
            )

            if row is None:
                return

            total = row["total_predictions"]
            correct = row["correct_predictions"] + (1 if was_correct else 0)
            accuracy = correct / total if total > 0 else 0.5

            # Adjust weight: linearly scale between MIN and MAX
            new_weight = MIN_WEIGHT + (MAX_WEIGHT - MIN_WEIGHT) * accuracy
            new_weight = round(new_weight, 4)

            await db.execute(
                """
                UPDATE model_performance
                SET correct_predictions = ?, accuracy = ?, weight = ?, last_updated = ?
                WHERE model_name = ? AND asset = ?
                """,
                (correct, round(accuracy, 4), new_weight, datetime.now(timezone.utc), model_name, asset),
            )
            await db.commit()
    except Exception as exc:
        logger.warning(f"record_outcome failed: {exc}")


async def get_all_performance() -> List[Dict]:
    try:
        async with get_db() as db:
            rows = await db.fetchall(
                "SELECT * FROM model_performance ORDER BY asset, model_name"
            )
        return list(rows)
    except Exception as exc:
        logger.warning(f"get_all_performance failed: {exc}")
        return []


async def evaluate_past_predictions(current_prices: Dict[str, float]):
    """Evaluate model predictions made ~1 hour ago against current prices.

    Queries model_outputs with `evaluated_at IS NULL` that are between 50 and
    70 minutes old, compares each model's signal to the price direction, and
    calls record_outcome() accordingly.  Marks each row as evaluated so it is
    not counted twice even across restarts.

    Args:
        current_prices: mapping of symbol → current price (e.g. {"BTC": 68500.0}).
    """
    if not current_prices:
        return

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=70)
    window_end = now - timedelta(minutes=50)

    try:
        async with get_db() as db:
            rows = await db.fetchall(
                """
                SELECT id, asset, model_name, signal, timestamp
                FROM model_outputs
                WHERE evaluated_at IS NULL
                  AND timestamp >= ?
                  AND timestamp <= ?
                """,
                (window_start, window_end),
            )

        for row in rows:
            asset = row["asset"]
            model_name = row["model_name"]
            signal = row["signal"]
            row_id = row["id"]
            pred_time = row["timestamp"]

            current_price = current_prices.get(asset)
            if current_price is None:
                continue

            # Retrieve the price closest to (but not after) the prediction timestamp
            async with get_db() as db:
                price_row = await db.fetchone(
                    """
                    SELECT price FROM price_data
                    WHERE symbol = ? AND timestamp <= ?
                    ORDER BY timestamp DESC LIMIT 1
                    """,
                    (asset, pred_time),
                )

                if price_row is None or not price_row["price"]:
                    continue

                old_price = float(price_row["price"])
                if old_price <= 0:
                    continue

                pct_change = (current_price - old_price) / old_price * 100

                if signal == "BUY":
                    was_correct = pct_change > _CORRECT_THRESHOLD_PCT
                elif signal == "SELL":
                    was_correct = pct_change < -_CORRECT_THRESHOLD_PCT
                else:  # HOLD — correct when price barely moved
                    was_correct = abs(pct_change) < 1.0

                await record_outcome(asset, model_name, was_correct)

                # Mark this output as evaluated so it is never double-counted
                await db.execute(
                    "UPDATE model_outputs SET evaluated_at = ? WHERE id = ?",
                    (now, row_id),
                )
                await db.commit()

            logger.debug(
                "Outcome: %s/%s signal=%s pct=%.2f%% correct=%s",
                model_name, asset, signal, pct_change, was_correct,
            )

    except Exception as exc:
        logger.warning("evaluate_past_predictions failed: %s", exc)
