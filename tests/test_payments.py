"""Payments + demand tests."""
import sys
sys.path.insert(0, ".")

from hv import demand as D
from hv.payments import adapters as A
from hv.payments import quotes as Q
from hv.payments import service as S


def test_fee_math_narrator_whole():
    b = Q.fee_breakdown(10.0)
    assert b == {"narrator_payout_usd": 10.0, "platform_commission_usd": 0.0,
                 "escrow_fee_usd": 0.03, "buyer_total_usd": 10.03, "donation_usd": 0.0}


def test_capability_honesty():
    st = A.StellarEscrow()
    assert st.capabilities()["supports_protected_funding"] is True
    assert st.capabilities()["production_enabled"] is False
    x = A.X402Base()
    assert x.capabilities()["supports_protected_funding"] is False
    svc = S.PaymentService(None)
    for ad in (st, x, A.StripeConnect(), A.Simulated()):
        svc.register(ad)
    for name in ("x402_base_usdc", "simulated"):
        try:
            svc.fund({}, name)
            assert False, name
        except (ValueError, KeyError):
            pass
    ok = svc.fund({"contract_id": "hvc_1", "payout_usd": 10}, "stellar_usdc_trustless_work_v1", test=True)
    assert ok["state"] == "testnet_intent"
    try:
        svc.fund({"contract_id": "hvc_1", "payout_usd": 10}, "stellar_usdc_trustless_work_v1")
        assert False, "production rail without test flag"
    except ValueError:
        pass


def test_demand_templates_match_agents():
    assert len(D.TEMPLATES) >= 5
    hits = D.match_templates(["horror", "storytelling"])
    assert hits and hits[0]["id"] == "horror-story"
    tasks = D.onboarding_tasks()
    assert tasks[0]["id"] == "base-sample" and len(tasks) > 4
