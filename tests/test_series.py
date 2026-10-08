"""Series + proof tests: enforcement by upload, validated portfolios."""
import sys
sys.path.insert(0, ".")

import pytest

from hv import proof as P
from hv import series as S


def test_series_lifecycle_enforced_by_upload():
    s = S.create_series("org", "ag", "nar", episodes=12, minutes_each=100,
                        price_each=11.0)
    assert s["total_value"] == 132.0
    with pytest.raises(ValueError):
        S.approve_episode(s, 1)  # no upload, nothing to approve
    S.submit_episode(s, 1, "a" * 64)
    r = S.approve_episode(s, 1)
    assert r == {"episode": 1, "released": 11.0, "series_progress": "1/12"}
    with pytest.raises(ValueError):
        S.approve_episode(s, 1)  # double approve blocked


def test_series_completion_and_health():
    s = S.create_series("org", "ag", "nar", episodes=2, minutes_each=10,
                        price_each=11.0)
    S.submit_episode(s, 1, "a" * 64, late=True)
    S.approve_episode(s, 1)
    h = S.series_health(s)
    assert h["progress"] == "1/2" and h["late_episodes"] == 1
    assert h["value_released"] == 11.0 and h["value_locked"] == 11.0
    S.submit_episode(s, 2, "b" * 64)
    S.approve_episode(s, 2)
    assert s["status"] == "completed"


def test_proof_requires_hash_and_tracks_views():
    with pytest.raises(AssertionError):
        P.proof_entry("hvc_1", "", "https://youtube.com/watch?v=x")
    e = P.proof_entry("hvc_1", "a" * 64, "https://youtube.com/watch?v=x", "Ep 1")
    P.record_views(e, 1000, "2026-10-01T00:00:00Z")
    P.record_views(e, 2500, "2026-10-08T00:00:00Z")
    pf = P.portfolio_proof([e])
    assert pf == {"validated_jobs": 1, "total_views": 2500,
                  "entries": [{"title": "Ep 1",
                               "video_url": "https://youtube.com/watch?v=x",
                               "views": 2500}]}


def test_master_mutual_enforcement_and_guarantee():
    m = S.master_agreement("org", "ag", "nar", episodes=15,
                           max_words_per_episode=1500, price_each=8.0,
                           minimum_guaranteed=10)
    assert m["rights"]["voice_cloning"] is False
    r = S.creator_supply_script(m, 1, late=True)
    assert r == {"episode": 1, "script supplied": True,
                 "deadline_shifted": True, "worker_penalty": "none"}
    st = S.settle_termination(m, completed_episodes=4)
    assert st == {"completed": 4, "guaranteed_minimum": 10,
                  "termination_owed_episodes": 6, "termination_value": 48.0}
    st2 = S.settle_termination(m, completed_episodes=12)
    assert st2["termination_owed_episodes"] == 0


def test_verification_levels():
    assert S.verify_publication(False, "u", True, True)["level"] is None
    assert S.verify_publication(True, "", False, False)["level"] == "platform"
    v = S.verify_publication(True, "https://youtube.com/watch?v=x", True, True)
    assert v["level"] == "publication" and v["public"] is True
    c = S.verify_publication(True, "u", True, True, oauth_channel=True)
    assert c["display"] == "Verified channel collaboration"
    priv = S.verify_publication(True, "", False, False, confidential=True)
    assert priv["level"] == "platform" and priv["public"] is False
