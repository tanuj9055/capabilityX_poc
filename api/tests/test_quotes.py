"""Pure quotation logic (no LLM): totals, pre-send checks, rule scoring, expiry, criteria validation."""
from datetime import datetime, timedelta, timezone

import pytest

from app import quotes

SNAP = {"line_items": [{"desc": "Distribution transformer 100 kVA", "qty": 10, "unit": "units"}],
        "requirements": [{"id": "r1", "text": "BIS certified", "type": "mandatory"},
                         {"id": "r2", "text": "OEM approvals", "type": "scored"}],
        "required_validity_days": 90}


def good(**kw):
    q = {"mode": "template", "lines": [{"desc": "Distribution transformer 100 kVA", "qty": 10, "unit": "units",
                                        "unit_price": 150000}],
         "gst_pct": 18, "freight": 5000, "lead_time_days": 30, "validity_days": 90,
         "payment_terms": "60 days credit", "payment_days": 60}
    q.update(kw)
    return quotes.clean_quotation(q, SNAP)


def codes(q, deadline=None):
    return {c["code"]: c["level"] for c in quotes.pre_send_checks(q, SNAP, deadline)}


def test_totals():
    t = good()["totals"]
    assert t == {"subtotal": 1500000.0, "tax": 270000.0, "freight": 5000.0, "landed_total": 1775000.0}


def test_clean_quote_passes_checks():
    assert codes(good()) == {}


def test_missing_price_is_error():
    q = good(lines=[{"desc": "Distribution transformer 100 kVA", "qty": 10, "unit": "units", "unit_price": None}])
    assert codes(q)["missing_price"] == "error"
    assert q["totals"]["subtotal"] == 0


def test_mandatory_deviation_is_error():
    q = good(compliance=[{"req_id": "r1", "response": "deviation", "note": "ISI pending"}])
    assert codes(q)["mandatory_deviation"] == "error"
    assert [c["req_id"] for c in q["compliance"]] == ["r1"]  # scored requirement not in the compliance list


def test_validity_checks():
    assert codes(good(validity_days=60))["short_validity"] == "error"
    assert codes(good(validity_days=None))["missing_validity"] == "error"  # RFQ states 90 days


def test_totals_mismatch_on_upload():
    assert codes(good(stated_total=1700000))["totals_mismatch"] == "error"
    assert "totals_mismatch" not in codes(good(stated_total=1775000))


def test_warnings_do_not_block():
    q = good(lead_time_days=None, payment_terms="", payment_days=None)
    c = codes(q)
    assert c == {"missing_lead_time": "warn", "missing_payment": "warn"}
    assert not quotes.has_errors(quotes.pre_send_checks(q, SNAP))


def test_deadline():
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    today = datetime.now(timezone.utc).date().isoformat()
    assert codes(good(), yesterday)["deadline_passed"] == "error"
    assert "deadline_passed" not in codes(good(), today)
    assert quotes.effective_status({"status": "sent", "deadline": yesterday}) == "expired"
    assert quotes.effective_status({"status": "viewed", "deadline": today}) == "viewed"
    assert quotes.effective_status({"status": "quoted", "deadline": yesterday}) == "quoted"


def test_rule_scoring_is_deterministic():
    qs = {"a": good(), "b": good(lines=[{"desc": "x", "qty": 10, "unit": "u", "unit_price": 200000}],
                                 lead_time_days=45, payment_days=30)}
    crit = quotes.validate_criteria(quotes.DEFAULT_CRITERIA)
    runs = [{c["id"]: quotes.score_rules(qs, c) for c in crit if c["kind"] != "descriptive"} for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    price, lead, pay = runs[0]["c1"], runs[0]["c2"], runs[0]["c3"]
    assert price["a"]["score"] == 100 and price["b"]["score"] < 100
    assert lead["a"]["score"] == 100 and lead["b"]["score"] == 50.0  # 15 days over a 30-day limit
    assert pay["a"]["score"] == 100 and pay["b"]["score"] == 50.0
    rows = {k: {c: v[k] for c, v in runs[0].items()} for k in qs}
    assert [k for k, _ in quotes.weighted(rows, crit)] == ["a", "b"]


def test_criteria_weights_must_total_100():
    bad = [dict(c) for c in quotes.DEFAULT_CRITERIA]
    bad[0]["weight"] = 40
    with pytest.raises(ValueError, match="total 100"):
        quotes.validate_criteria(bad)
    with pytest.raises(ValueError, match="describe"):
        quotes.validate_criteria([{"name": "x", "kind": "descriptive", "weight": 100}])
    with pytest.raises(ValueError, match="limit"):
        quotes.validate_criteria([{"name": "x", "kind": "threshold", "field": "lead_time_days", "weight": 100}])
