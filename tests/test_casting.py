"""Casting tests: roles, sides, direction, multi-role lists."""
import sys
sys.path.insert(0, ".")

from hv import casting as C


def test_role_side_frozen():
    r = C.role("film1", "Wizard", "You shall not pass!", {"trait": "old"})
    assert r["side_sha256"] and r["lines_count"] == 4


def test_cast_list_matches_characters():
    roles = [C.role("film1", "Wizard", "...", {"trait": "old"}),
             C.role("film1", "Imp", "...", {"trait": "squeaky"})]
    cat = [{"voice_id": "v1", "handle": "a",
            "characters": ["old wizard", "narrator"]}]
    out = C.cast_list("film1", roles, cat)
    assert out[0]["candidates"][0]["voice_id"] == "v1"
    assert out[0]["candidates"][0]["matched_character"] == "old wizard"
    assert out[1]["candidates"] == []


def test_stage_direction_versioned():
    sd = C.stage_direction("hvc_1", "Play it tired, not sleepy.")
    assert sd["sha256"] and sd["contract_id"] == "hvc_1"


def test_pickup_pricing():
    assert C.pickup_price(3) == {"lines": 3, "price_usd": 3.0, "flow": "corrections"}
    assert C.pickup_price(1)["price_usd"] == 2.0
