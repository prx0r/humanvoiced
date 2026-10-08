"""Audition tests: sides, submissions, comparison, decision."""
import sys
sys.path.insert(0, ".")

import pytest

from hv import audition as A


def test_side_length_capped():
    with pytest.raises(ValueError):
        A.casting_call("p", "r", "word " * 40, "2030-01-01T00:00:00Z")
    c = A.casting_call("film1", "Wizard", "You shall not pass friend", "2030-01-01T00:00:00Z")
    assert c["side_sha256"] and not c["decision"]


def test_submit_compare_decide():
    c = A.casting_call("film1", "Wizard", "short side here", "2030-01-01T00:00:00Z")
    A.submit_read(c, "nar_a", "a" * 64)
    A.submit_read(c, "nar_b", "b" * 64)
    rows = A.compare(c)
    assert [r["narrator_id"] for r in rows] == ["nar_a", "nar_b"]
    assert all(r["side_sha256"] == c["side_sha256"] for r in rows)
    with pytest.raises(ValueError):
        A.decide(c, "nar_x")
    d = A.decide(c, "nar_a", "best take")
    assert d["winner"] == "nar_a"
    with pytest.raises(ValueError):
        A.submit_read(c, "nar_c", "c" * 64)
