import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from db import get_db
from models.schemas import ModelPerformance, ConsensusResult

logger = logging.getLogger(__name__)

MODEL_NAMES = ["openai", "claude", "gemini"]
DEFAULT_WEIGHT = 1.0
MIN_WEIGHT = 0.2
MAX_WEIGHT = 2.0


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
                (model_name, asset, datetime.utcnow(), datetime.utcnow()),
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
                (correct, round(accuracy, 4), new_weight, datetime.utcnow(), model_name, asset),
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
