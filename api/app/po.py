"""Purchase orders from the selected quotation — the pure (no-LLM) parts.

- buyer profile defaults, incl. the standard terms library (generic clauses of the buyer's PO templates,
  Purchase_Order_Template_*.docx; the AI only selects from this saved text, it never writes clauses)
- from_quote: the standard PO built from the selected quotation + RFQ + buyer profile
- clean: normalise what the client sends; items / quantities / prices stay locked to the quotation
  (template + AI modes), only an uploaded PO carries its own lines, which are then compared
- checks: the same pre-issue checks for all three modes (BRD criteria 3, 10, 11)
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from . import quotes

MODES = ("template", "ai", "upload")
REQUIRED = {  # field: label — the PO cannot be issued while one is empty
    "po_number": "PO number", "po_date": "PO date", "buyer_name": "Buyer name",
    "buyer_address": "Buyer registered office", "bill_to": "Bill-to address", "ship_to": "Ship-to address",
    "supplier_name": "Supplier", "delivery_date": "Required delivery date", "payment_terms": "Payment terms",
    "buyer_signatory": "Buyer authorised signatory",
}
TEXT_FIELDS = ("po_number", "po_date", "po_type", "buyer_name", "buyer_address", "buyer_gstin", "bill_to", "ship_to",
               "delivery_basis", "payment_terms", "currency", "supplier_name", "supplier_address", "supplier_gstin",
               "supplier_code", "supplier_contact", "quote_ref", "delivery_date", "inspection", "special_terms",
               "notes", "buyer_signatory", "buyer_designation", "intro")
OPEN_FIELDS = ("po_type", "delivery_basis", "inspection", "special_terms", "notes")  # what a saved template keeps

# Generic clauses from the buyer's PO templates (sections 8, 11, 12, 13 and 15). Sector-specific clauses
# (AS9100, IPC, ESD ...) are left out; the buyer adds their own in the profile.
DEFAULT_TERMS = [
    ("t1", "Acknowledgement", "The Supplier shall acknowledge this PO within five working days and identify any "
     "requested correction. Starting work or accepting a release constitutes acceptance of the applicable PO terms."),
    ("t2", "Invoicing", "Invoice only accepted goods and accepted milestone deliverables against the applicable PO line. "
     "Each invoice must state the PO number, item, quantity, delivery reference, HSN, GST rate, Supplier GSTIN, Udyam "
     "status and bank details. Buyer may withhold disputed amounts while paying undisputed amounts."),
    ("t3", "MSME payment protection", "Where the Supplier is a qualifying micro or small enterprise, payment shall be made "
     "within the period required by the MSMED Act 2006. Applicable law prevails over any inconsistent wording. Supplier "
     "shall immediately notify Buyer of any change in Udyam classification."),
    ("t4", "Warranty", "Warranty is 12 months from delivery for defects attributable to Supplier material or workmanship, "
     "without limiting longer statutory or latent-defect rights. Buyer may reject nonconforming goods and require "
     "rework, replacement or credit."),
    ("t5", "Change control and subcontracting", "No change to design, material source, process, manufacturing site or "
     "sub-tier supplier without prior written Buyer approval. Subcontracting does not relieve the Supplier of quality, "
     "delivery or confidentiality responsibility."),
    ("t6", "Confidentiality", "Drawings, specifications, prices and Buyer information are confidential and may be accessed "
     "only by authorised personnel for PO performance. No copying, external transfer or publicity without Buyer approval."),
    ("t7", "Title and risk", "Title and risk for conforming goods pass at the point stated in the delivery term, subject to "
     "Buyer inspection and acceptance. Buyer-owned property remains Buyer property at all times."),
    ("t8", "Force majeure", "Neither party is liable for delay caused by a genuine force-majeure event beyond reasonable "
     "control if prompt notice, mitigation and recovery information are provided. Price or routine capacity shortage "
     "alone is not force majeure."),
    ("t9", "Termination", "Buyer may terminate for supplier breach, insolvency, unauthorised change, repeated delivery or "
     "quality failure, or legal noncompliance after any applicable cure period. On termination for convenience, Buyer "
     "will pay for accepted goods and approved unavoidable work in process."),
    ("t10", "Assignment", "The Supplier shall not assign this PO, receivables or material performance obligations without "
     "Buyer consent, except for an approved invoice-financing arrangement that does not change Buyer obligations."),
    ("t11", "Ethics and legal compliance", "Comply with applicable labour, wage, safety, environmental, anti-bribery and "
     "waste-management laws. Child labour, forced labour, bribery and counterfeit material are prohibited."),
    ("t12", "Insurance and indemnity", "Supplier shall maintain commercially appropriate product liability, transit and "
     "property insurance, and indemnify Buyer against third-party claims to the extent caused by supplier breach, "
     "negligence or violation of law."),
    ("t13", "Disputes", "The parties will first escalate disputes through their commercial leaders. Governing law and "
     "dispute forum are [insert agreed Indian jurisdiction and arbitration or court forum]."),
]
PLACEHOLDER = re.compile(r"\[(insert|to be|tbd)[^\]]*\]", re.I)


# ── buyer profile ────────────────────────────────────────────────────────────
def default_profile(bid: str, name: str) -> dict:
    return {"id": bid, "name": name, "registered_office": "", "gstin": "", "billing_address": "",
            "shipping_addresses": [], "contact": "", "signatory_name": "", "signatory_designation": "",
            "terms": [{"id": i, "title": t, "text": x, "default": True} for i, t, x in DEFAULT_TERMS],
            "po_templates": []}


def clean_profile(p: dict, base: dict) -> dict:
    out = dict(base)
    for k in ("name", "registered_office", "gstin", "billing_address", "contact", "signatory_name",
              "signatory_designation"):
        if k in p:
            out[k] = str(p.get(k) or "").strip()[:500]
    if "shipping_addresses" in p:
        out["shipping_addresses"] = [str(x).strip()[:500] for x in p.get("shipping_addresses") or [] if str(x).strip()][:10]
    if "terms" in p:
        terms, seen = [], set()
        for i, t in enumerate(p.get("terms") or []):
            title, text = str(t.get("title") or "").strip()[:120], str(t.get("text") or "").strip()[:3000]
            if not (title and text):
                continue
            tid = str(t.get("id") or "") or f"c{i + 1}"
            while tid in seen:
                tid += "x"
            seen.add(tid)
            terms.append({"id": tid, "title": title, "text": text, "default": bool(t.get("default", True))})
        out["terms"] = terms
    return out


def code(name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name or "")
    c = "".join(w[0] for w in words if w.lower() not in ("pvt", "private", "ltd", "limited")).upper()
    return (c if len(c) >= 2 else (name or "BUY").upper().replace(" ", ""))[:6] or "BUY"


def po_number(profile: dict, seq: int) -> str:
    return f"{code(profile['name'])}-PO-{date.today().year}-{seq:04d}"


# ── quotation facts ──────────────────────────────────────────────────────────
def quote_ref(req: dict) -> str:
    d = (req.get("submitted_at") or "")[:10]
    return f"Quotation rev {req.get('revision') or 1} dated {d}" if d else "Submitted quotation"


def valid_until(req: dict) -> date | None:
    v = (req.get("quotation") or {}).get("validity_days")
    if not v or not req.get("submitted_at"):
        return None
    return datetime.fromisoformat(req["submitted_at"][:10]).date() + timedelta(days=int(v))


def quote_lines(req: dict) -> list[dict]:
    return [{k: li.get(k) for k in ("desc", "qty", "unit", "unit_price", "amount")} for li in req["quotation"]["lines"]]


# ── building the PO ──────────────────────────────────────────────────────────
def from_quote(req: dict, rfq: dict, seller: dict, profile: dict, seq: int) -> dict:
    """The standard PO: everything the quotation, the RFQ and the buyer profile already say."""
    q, u = req["quotation"], rfq.get("understanding") or {}
    ships = profile.get("shipping_addresses") or []
    lead = q.get("lead_time_days")
    qty = sum(li.get("qty") or 0 for li in q["lines"] if li.get("unit") != "lot")
    pay = q.get("payment_terms") or (f"{q['payment_days']:g} days credit" if q.get("payment_days") else "")
    f = {
        "po_number": po_number(profile, seq), "po_date": date.today().isoformat(), "po_type": "Standard purchase order",
        "buyer_name": profile.get("name") or rfq.get("buyer_name") or "", "buyer_address": profile.get("registered_office", ""),
        "buyer_gstin": profile.get("gstin", ""), "bill_to": profile.get("billing_address") or profile.get("registered_office", ""),
        "ship_to": ships[0] if len(ships) == 1 else "",
        "delivery_basis": u.get("commercial_terms") or "", "payment_terms": pay, "currency": "INR",
        "supplier_name": seller["name"], "supplier_address": seller.get("city", ""), "supplier_gstin": "",
        "supplier_code": "", "supplier_contact": "", "quote_ref": quote_ref(req), "delivery_date": "",
        "inspection": "", "special_terms": "", "notes": "", "buyer_signatory": profile.get("signatory_name", ""),
        "buyer_designation": profile.get("signatory_designation", ""),
        "intro": f"{profile.get('name') or 'The Buyer'} places this order on {seller['name']} for the supply of "
                 f"{u.get('item') or rfq['title']} against {rfq['ref']} and the supplier's {quote_ref(req).lower()}, "
                 "on the terms below.",
    }
    return {
        "fields": f,
        "lines": quote_lines(req), "gst_pct": q.get("gst_pct") or 0, "freight": q.get("freight") or 0,
        "key_controls": ["No change to the ordered items, quantities or prices without a written PO amendment.",
                         "Goods are accepted only after Buyer inspection; payment does not waive defects."],
        "schedule": [["Supply", f"{qty:,.0f} units" if qty else "As per PO lines",
                      f"Within {lead:g} days of PO" if lead else "", "Receipt and acceptance of conforming goods"]],
        "clarifications": ([["Supplier assumptions", q["assumptions"]]] if q.get("assumptions") else [])
                          + [[c["text"], f"Deviation accepted: {c.get('note') or 'as quoted'}"]
                             for c in q.get("compliance") or [] if c.get("response") == "deviation"],
        "terms": [{"id": t["id"], "title": t["title"], "text": t["text"]} for t in profile.get("terms") or []
                  if t.get("default", True)],
    }


def apply_template(po: dict, tpl: dict, profile: dict) -> dict:
    """A saved PO template keeps the open fields, key controls and the chosen clauses."""
    for k in OPEN_FIELDS:
        if tpl.get("fields", {}).get(k):
            po["fields"][k] = tpl["fields"][k]
    if tpl.get("key_controls"):
        po["key_controls"] = list(tpl["key_controls"])
    lib = {t["id"]: t for t in profile.get("terms") or []}
    if tpl.get("term_ids") is not None:
        po["terms"] = [{k: lib[i][k] for k in ("id", "title", "text")} for i in tpl["term_ids"] if i in lib]
    return po


def template_from_po(po: dict, name: str, tid: str) -> dict:
    return {"id": tid, "name": name[:80], "fields": {k: po["fields"].get(k, "") for k in OPEN_FIELDS},
            "key_controls": list(po.get("key_controls") or []), "term_ids": [t["id"] for t in po.get("terms") or []]}


SCHEDULE_COLS = ["Stage", "Quantity", "Required timing", "Release and acceptance gate"]
CLARIFY_COLS = ["Quotation topic", "Buyer position and PO condition"]


def _rows(v, cols) -> list[list[str]]:
    n, out = len(cols), []
    for r in v if isinstance(v, list) else []:
        if isinstance(r, dict):
            r = list(r.values())
        if isinstance(r, list):
            cells = [str(c if c is not None else "").strip()[:800] for c in r][:n]
            cells += [""] * (n - len(cells))
            if any(cells) and [c.lower() for c in cells] != [c.lower() for c in cols]:  # drop an echoed header row
                out.append(cells)
    return out[:30]


def clean(po: dict, body: dict, req: dict) -> dict:
    """Merge the buyer's edits into the PO. Lines are re-copied from the quotation unless it is an upload."""
    f = dict(po.get("fields") or {})
    for k in TEXT_FIELDS:
        if k in (body.get("fields") or {}):
            f[k] = str(body["fields"].get(k) or "").strip()[:2000]
    po["fields"] = f
    if po.get("mode") == "upload":
        if "lines" in body:
            po["lines"] = [{"desc": str(li.get("desc") or "").strip(), "qty": quotes._f(li.get("qty")) or 0,
                            "unit": str(li.get("unit") or "units")[:20], "unit_price": quotes._f(li.get("unit_price"))}
                           for li in body.get("lines") or [] if str(li.get("desc") or "").strip()]
        for k in ("gst_pct", "freight", "stated_total"):
            if k in body:
                po[k] = quotes._f(body.get(k))
    else:  # template / AI: items, quantities, prices, taxes are the quotation's and cannot be edited
        q = req["quotation"]
        po["lines"], po["gst_pct"], po["freight"] = quote_lines(req), q.get("gst_pct") or 0, q.get("freight") or 0
    if "key_controls" in body:
        po["key_controls"] = [str(x).strip()[:600] for x in body.get("key_controls") or [] if str(x).strip()][:15]
    if "schedule" in body:
        po["schedule"] = _rows(body["schedule"], SCHEDULE_COLS)
    if "clarifications" in body:
        po["clarifications"] = _rows(body["clarifications"], CLARIFY_COLS)
    if "terms" in body:
        po["terms"] = [{"id": str(t.get("id") or ""), "title": str(t.get("title") or "").strip()[:120],
                        "text": str(t.get("text") or "").strip()[:3000]}
                       for t in body.get("terms") or [] if str(t.get("title") or "").strip()][:30]
    po["totals"] = totals(po)
    return po


def totals(po: dict) -> dict:
    sub = 0.0
    for li in po.get("lines") or []:
        li["amount"] = round((li.get("qty") or 0) * li["unit_price"], 2) if li.get("unit_price") is not None else None
        sub += li["amount"] or 0
    tax = round(sub * (po.get("gst_pct") or 0) / 100, 2)
    fr = po.get("freight") or 0
    return {"subtotal": round(sub, 2), "tax": tax, "freight": fr, "total": round(sub + tax + fr, 2)}


# ── checks ───────────────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    s = re.sub(r"\b(m/?s|pvt|private|ltd|limited|llp|co|company|the|and|&)\b", " ", str(s or "").lower())
    return re.sub(r"[^a-z0-9]+", "", s)


def compare(po: dict, req: dict) -> list[str]:
    """Differences between a PO's own data and the selected quotation: supplier, items, quantities, prices, totals."""
    out, q = [], req["quotation"]
    sup, want = _norm(po["fields"].get("supplier_name")), _norm(req["seller_name"])
    if not sup or not (want in sup or sup in want):
        out.append(f"Supplier “{po['fields'].get('supplier_name') or '—'}” is not the selected supplier “{req['seller_name']}”")
    ql, pl = q["lines"], po.get("lines") or []
    if len(pl) != len(ql):
        out.append(f"The PO has {len(pl)} item line(s); the quotation has {len(ql)}")
    for i, (a, b) in enumerate(zip(pl, ql), 1):
        if abs((a.get("qty") or 0) - (b.get("qty") or 0)) > 1e-6:
            out.append(f"Line {i} quantity {a.get('qty') or 0:g} ≠ quoted {b.get('qty') or 0:g}")
        if a.get("unit_price") is None or abs(a["unit_price"] - (b.get("unit_price") or 0)) > 0.005:
            out.append(f"Line {i} unit price ₹{a.get('unit_price') or 0:,.2f} ≠ quoted ₹{b.get('unit_price') or 0:,.2f}")
    t, qt = po["totals"], q["totals"]
    if abs((po.get("gst_pct") or 0) - (q.get("gst_pct") or 0)) > 1e-6:
        out.append(f"GST {po.get('gst_pct') or 0:g}% ≠ quoted {q.get('gst_pct') or 0:g}%")
    if abs(t["total"] - qt["landed_total"]) > 1:
        out.append(f"PO total ₹{t['total']:,.2f} ≠ quotation total ₹{qt['landed_total']:,.2f}")
    st = po.get("stated_total")
    if st is not None and abs(st - t["total"]) > max(1.0, 0.005 * st):
        out.append(f"Total stated in the uploaded file ₹{st:,.2f} ≠ the PO lines ₹{t['total']:,.2f}")
    return out


def checks(po: dict, req: dict, today: date | None = None) -> list[dict]:
    """[{level, code, message}] — Generate PO is refused while any error remains. Same for all three modes."""
    out, f = [], po.get("fields") or {}

    def add(level, c, msg):
        out.append({"level": level, "code": c, "message": msg})
    if po.get("mode") not in MODES:
        add("error", "no_mode", "Choose how to create the PO: template, AI-assisted draft or upload")
        return out
    for k, label in REQUIRED.items():
        if not str(f.get(k) or "").strip():
            add("error", "missing_field", f"{label} is required")
    vu = valid_until(req)
    if vu is None:
        add("warn", "validity_unknown", "The quotation does not state a validity period")
    elif (today or date.today()) > vu:
        add("error", "quote_expired", f"The quotation expired on {vu.isoformat()} — ask the supplier to revalidate it")
    if not po.get("lines"):
        add("error", "no_lines", "The PO has no item lines")
    for m in compare(po, req):
        add("error", "mismatch", m)
    texts = [str(v) for v in f.values()] + [t["text"] for t in po.get("terms") or []] + po.get("key_controls", [])
    texts += [c for r in po.get("schedule", []) + po.get("clarifications", []) for c in r]
    if any(PLACEHOLDER.search(x) for x in texts):
        add("error", "placeholder", "Replace the [insert …] placeholders (e.g. in the Disputes clause) before issue")
    if po.get("mode") == "upload" and not po.get("file"):
        add("error", "no_file", "Upload the PO file")
    if not f.get("buyer_gstin"):
        add("warn", "missing_gstin", "Buyer GSTIN is not stated")
    if not po.get("terms"):
        add("warn", "no_terms", "No terms and conditions are attached")
    return out


def has_errors(c: list[dict]) -> bool:
    return any(x["level"] == "error" for x in c)


def questions(po: dict, profile: dict) -> list[dict]:
    """What the AI-assisted draft cannot fill from the quotation, the RFQ and the profiles (BRD criterion 9)."""
    f, out = po["fields"], []
    ships = profile.get("shipping_addresses") or []
    if not f.get("ship_to"):
        out.append({"id": "ship_to", "question": "Which address should the goods be shipped to?",
                    **({"options": ships} if len(ships) > 1 else {})})
    if not f.get("delivery_date"):
        out.append({"id": "delivery_date", "question": "What is the required delivery date?", "type": "date"})
    for k, q in (("buyer_address", "What is your registered office address?"),
                 ("bill_to", "Which billing address should the supplier invoice?"),
                 ("buyer_signatory", "Who signs this PO for you (name)?")):
        if not f.get(k):
            out.append({"id": k, "question": q})
    out.append({"id": "inspection", "question": "Any inspection or acceptance requirements for this order? "
                                                "(e.g. pre-dispatch inspection, test certificates) — optional"})
    out.append({"id": "special_terms", "question": "Any special terms for this order? — optional"})
    return out
