from typing import List, Dict
from collections import Counter
from datetime import datetime, timezone
from models.schemas import ModelOutput, ConsensusResult


def compute_consensus(
    asset: str,
    outputs: List[ModelOutput],
    model_weights: Dict[str, float] = None,
) -> ConsensusResult:
    if not outputs:
        return ConsensusResult(
            asset=asset,
            final_signal="HOLD",
            confidence=0.5,
            agreement_level="low",
            models={},
            dissenting_models=[],
            timestamp=datetime.now(timezone.utc),
        )

    weights = model_weights or {}
    weighted_scores: Dict[str, float] = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
    total_weight = 0.0
    models_detail: Dict = {}
    signal_votes: List[str] = []

    for out in outputs:
        w = weights.get(out.model_name, 1.0)
        sig = out.signal
        if sig not in weighted_scores:
            sig = "HOLD"
        weighted_scores[sig] += w * out.confidence
        total_weight += w
        signal_votes.append(sig)
        models_detail[out.model_name] = {
            "signal": out.signal,
            "confidence": out.confidence,
            "reasoning": out.reasoning,
        }

    # Determine final signal by weighted score
    final_signal = max(weighted_scores, key=lambda k: weighted_scores[k])

    # Weighted average confidence
    winner_weight_sum = sum(
        weights.get(o.model_name, 1.0) * o.confidence
        for o in outputs if o.signal == final_signal
    )
    winner_count = sum(weights.get(o.model_name, 1.0) for o in outputs if o.signal == final_signal)
    avg_confidence = winner_weight_sum / winner_count if winner_count else 0.5

    # Agreement level
    vote_counts = Counter(signal_votes)
    majority_count = vote_counts.get(final_signal, 0)
    n = len(outputs)
    if majority_count == n:
        agreement_level = "high"
    elif majority_count >= n / 2:
        agreement_level = "medium"
    else:
        agreement_level = "low"

    dissenting = [o.model_name for o in outputs if o.signal != final_signal]

    return ConsensusResult(
        asset=asset,
        final_signal=final_signal,
        confidence=round(avg_confidence, 4),
        agreement_level=agreement_level,
        models=models_detail,
        dissenting_models=dissenting,
        timestamp=datetime.now(timezone.utc),
    )
