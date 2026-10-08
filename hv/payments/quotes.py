"""Fee math: narrator 100%, provider/donor funds cover the rest."""
from __future__ import annotations

ESCROW_FEE_BPS = 30  # Trustless Work published 0.3%/release


def fee_breakdown(payout_usd: float, escrow_bps: int = ESCROW_FEE_BPS) -> dict:
    escrow_fee = round(payout_usd * escrow_bps / 10000, 2)
    return {"narrator_payout_usd": round(payout_usd, 2),
            "platform_commission_usd": 0.0,
            "escrow_fee_usd": escrow_fee,
            "buyer_total_usd": round(payout_usd + escrow_fee, 2),
            "donation_usd": 0.0}
