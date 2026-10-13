"""Pure PO logic (no LLM): standard PO from the quotation, locked lines, pre-issue checks, upload comparison."""
from datetime import date, timedelta

from app import po, quotes

SNAP = {"line_items": [{"desc": "Distribution transformer 100 kVA", "qty": 10, "unit": "units"}],
        "requirements": [], "required_validity_days": None}
RFQ = {"id": "r1", "ref": "RFQ-2026-AAAAA", "title": "Distribution transformers", "buyer_name": "VoltEdge",
       "understanding": {"item": "Distribution transformer 100 kVA", "commercial_terms": "FOR buyer plant"}}
SELLER = {"id": "ref-remi", "name": "Remi", "city": "Bhopal"}


def req(validity=90, submitted=None):
    q = quotes.clean_quotation({"lines": [{"desc": "Distribution transformer 100 kVA", "qty": 10, "unit": "units",
                                           "unit_price": 150000}], "gst_pct": 18, "freight": 5000,
                                "lead_time_days": 45, "validity_days": validity, "payment_terms": "60 days credit",
                                "assumptions": "CRGO price as of October"}, SNAP)
    return {"id": "q1", "seller_id": "ref-remi", "seller_name": "Remi", "quotation": q, "revision": 1,
            "submitted_at": (submitted or date.today()).isoformat() + "T10:00:00+00:00"}


def profile(**kw):
    p = po.default_profile("voltedge", "VoltEdge Power Pvt Ltd")
    p.update({"registered_office": "Plot 4, Pune", "billing_address": "Accounts, Plot 4, Pune",
              "shipping_addresses": ["Plant 1, Chakan"], "signatory_name": "A. Rao", "gstin": "27AAAAA0000A1Z5"}, **kw)
    p["terms"] = [t for t in p["terms"] if t["id"] != "t13"]  # the Disputes clause has an [insert ...] placeholder
    return p


def standard(r=None, prof=None):
    r = r or req()
    p = {"mode": "template", "rfq": RFQ, **po.from_quote(r, RFQ, SELLER, prof or profile(), 1)}
    return po.clean(p, {}, r), r


def codes(p, r):
    return {c["code"] for c in po.checks(p, r) if c["level"] == "error"}


def test_standard_po_is_prefilled_from_quote_and_profile():
    p, r = standard()
    f = p["fields"]
    assert f["supplier_name"] == "Remi" and f["buyer_name"] == "VoltEdge Power Pvt Ltd"
    assert f["ship_to"] == "Plant 1, Chakan"  # one shipping address -> filled, not asked
    assert f["payment_terms"] == "60 days credit" and f["po_number"] == f"VP-PO-{date.today().year}-0001"
    assert p["totals"]["total"] == r["quotation"]["totals"]["landed_total"] == 1775000
    assert p["clarifications"][0][1] == "CRGO price as of October"


def test_lines_are_locked_to_the_quotation():
    p, r = standard()
    p = po.clean(p, {"lines": [{"desc": "x", "qty": 999, "unit": "u", "unit_price": 1}], "gst_pct": 0}, r)
    assert p["lines"][0]["qty"] == 10 and p["lines"][0]["unit_price"] == 150000 and p["gst_pct"] == 18


def test_required_fields_and_delivery_date():
    p, r = standard()
    assert codes(p, r) == {"missing_field"}  # only the delivery date is open
    p = po.clean(p, {"fields": {"delivery_date": "2026-12-01"}}, r)
    assert codes(p, r) == set()
    p = po.clean(p, {"fields": {"ship_to": ""}}, r)
    assert "missing_field" in codes(p, r)


def test_expired_quotation_blocks_issue():
    r = req(validity=30, submitted=date.today() - timedelta(days=40))
    p, _ = standard(r)
    p = po.clean(p, {"fields": {"delivery_date": "2026-12-01"}}, r)
    assert codes(p, r) == {"quote_expired"}


def test_placeholder_in_terms_blocks_issue():
    p, r = standard(prof=profile())
    p = po.clean(p, {"fields": {"delivery_date": "2026-12-01"},
                     "terms": [{"id": "t13", "title": "Disputes", "text": "Forum: [insert agreed forum]"}]}, r)
    assert codes(p, r) == {"placeholder"}


def test_upload_mismatches_are_flagged():
    r = req()
    p = {"mode": "upload", "rfq": RFQ, "file": {"name": "po.pdf", "ext": "pdf"}, "fields": {}, "terms": []}
    good = {"fields": {k: "x" for k in po.REQUIRED} | {"supplier_name": "M/s Remi", "delivery_date": "2026-12-01"},
            "lines": [{"desc": "Transformer", "qty": 10, "unit": "units", "unit_price": 150000}],
            "gst_pct": 18, "freight": 5000}
    p = po.clean(p, good, r)
    assert codes(p, r) == set()  # "M/s Remi" is the same supplier
    bad = po.clean(dict(p), {**good, "fields": {**good["fields"], "supplier_name": "KCS"},
                             "lines": [{"desc": "Transformer", "qty": 12, "unit": "units", "unit_price": 140000}]}, r)
    msgs = [c["message"] for c in po.checks(bad, r) if c["code"] == "mismatch"]
    assert any("Supplier" in m for m in msgs) and any("quantity" in m for m in msgs)
    assert any("unit price" in m for m in msgs) and any("total" in m for m in msgs)


def test_ai_questions_ask_only_what_is_unknown():
    p, _ = standard()
    ids = [q["id"] for q in po.questions(p, profile())]
    assert ids == ["delivery_date", "inspection", "special_terms"]  # ship-to, addresses, signatory known
    two = profile(shipping_addresses=["Plant 1", "Plant 2"])
    p2, _ = standard(prof=two)
    qs = {q["id"]: q for q in po.questions(p2, two)}
    assert qs["ship_to"]["options"] == ["Plant 1", "Plant 2"]
    assert not {"supplier_name", "lines", "payment_terms"} & set(qs)


def test_saved_template_keeps_open_fields_and_clauses():
    p, r = standard()
    p = po.clean(p, {"fields": {"inspection": "Pre-dispatch inspection", "po_type": "Blanket purchase order"},
                     "terms": [p["terms"][0]]}, r)
    tpl = po.template_from_po(p, "Transformers", "tp1")
    q, _ = standard()
    q = po.apply_template(q, tpl, profile())
    assert q["fields"]["inspection"] == "Pre-dispatch inspection" and [t["id"] for t in q["terms"]] == ["t1"]
