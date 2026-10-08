"""Reputation outcome vector R_n=(Q,D,A,S,C) + contract-specific matcher M(n,j).

Windows: 90-day operational score + 365-day history. New voices get the
'new_voice' label, never a low score. Declines/offline cost nothing.
Verified outcomes only; disputed/platform-caused incidents excluded.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DIMENSIONS = ("Q", "D", "A", "S", "C")
MATCH_WEIGHTS = {"VoiceFit": 0.35, "Reliability": 0.25, "Availability": 0.20,
                 "PriceFit": 0.10, "Preferences": 0.10}


@dataclass
class ReputationVector:
    narrator_id: str
    window_days: int = 90
    completed: int = 0
    vector: dict = field(default_factory=lambda: {d: None for d in DIMENSIONS})
    verified_incidents: int = 0
    appeals_won: int = 0
    model_version: str = "rn-v1"

    @property
    def history_label(self) -> str:
        if self.completed == 0:
            return "new_voice"
        if self.completed < 5:
            return "insufficient_history"
        return "established"

    def record_outcome(self, outcome: dict) -> None:
        """outcome: {verified: bool, worker_fault: bool, scores: {dim: 0-1}}."""
        if not outcome.get("verified"):
            return  # operational incidents stay private until verified
        self.completed += 1
        scores = outcome.get("scores", {})
        n = self.completed
        for d in DIMENSIONS:
            if d in scores:
                prev = self.vector[d]
                self.vector[d] = scores[d] if prev is None else prev + (scores[d] - prev) / n
        if outcome.get("worker_fault"):
            self.verified_incidents += 1

    def apply_appeal(self, correction: dict) -> None:
        """Successful appeals correct history (metrics recomputed by caller)."""
        self.appeals_won += 1
        for d, v in correction.get("scores", {}).items():
            if d in self.vector:
                self.vector[d] = v
        if correction.get("clear_incident"):
            self.verified_incidents = max(0, self.verified_incidents - 1)

    def to_dict(self) -> dict:
        return {"narrator_id": self.narrator_id, "window_days": self.window_days,
                "completed": self.completed, "history_label": self.history_label,
                "vector": dict(self.vector), "verified_incidents": self.verified_incidents,
                "appeals_won": self.appeals_won, "model_version": self.model_version}


def match_score(features: dict) -> float:
    """M(n,j): contract-specific fit from named features (starting weights)."""
    return round(sum(features.get(k, 0.0) * w for k, w in MATCH_WEIGHTS.items()), 4)
