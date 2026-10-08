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
