"""Quote requests, quotations and quote evaluation — the pure (no-LLM) parts.

- line_items / snapshot: frozen copy of the approved RFQ sent with each quote request
- compute_totals: line amounts, GST, freight, landed total — by rule only
- pre_send_checks: BRD §6 checks (missing price, mandatory deviation, short validity, totals mismatch)
- score_rules: numeric + threshold criteria; same input -> same output
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

STATUSES = ("sent", "viewed", "quoted", "declined", "expired")
FIELDS = {  # numeric quote fields a rule criterion can use, with their natural direction
    "landed_total": {"label": "Total landed price (₹)", "better": "lower"},
    "lead_time_days": {"label": "Lead time (days)", "better": "lower"},
    "payment_days": {"label": "Payment credit (days)", "better": "higher"},
    "validity_days": {"label": "Quote validity (days)", "better": "higher"},
    "min_order": {"label": "Minimum order (units)", "better": "lower"},
}
DEFAULT_CRITERIA = [
    {"id": "c1", "name": "Total landed price", "kind": "numeric", "field": "landed_total", "better": "lower",
     "weight": 50, "description": "Lowest total landed price scores highest"},
    {"id": "c2", "name": "Delivery lead time", "kind": "threshold", "field": "lead_time_days", "limit": 30,
     "weight": 20, "description": "Delivery within 30 days scores full, less after"},
    {"id": "c3", "name": "Payment credit", "kind": "numeric", "field": "payment_days", "better": "higher",
     "weight": 10, "description": "Longer payment credit scores higher"},
    {"id": "c4", "name": "Relevant past experience & compliance", "kind": "descriptive", "weight": 20,
     "description": "Relevant past supply experience for this item and full compliance with the RFQ's "
                    "mandatory requirements, with no deviations"},
]


# ── snapshot ─────────────────────────────────────────────────────────────────
def _num(s) -> float | None:
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(s or ""))
    return float(m.group().replace(",", "")) if m else None


def line_items(rfq: dict) -> list[dict]:
    """One quotation line per item the RFQ buys (the RFQs here buy a single item line)."""
    u = rfq.get("understanding") or {}
    desc = u.get("item") or rfq.get("title") or "Item"
    qty_txt = u.get("quantity") or ""
    qty = _num(qty_txt)
    unit = (re.sub(r"[\d,.\s]+", " ", qty_txt).strip().split(" ")[0] if qty_txt else "") or "units"
    return [{"desc": desc, "qty": qty or 1, "unit": unit[:20]}]


def required_validity(rfq: dict) -> int | None:
    u = rfq.get("understanding") or {}
    txt = " ".join(str(u.get(k) or "") for k in ("commercial_terms", "evaluation_basis"))
    m = re.search(r"valid\w*[^.]{0,40}?(\d{2,3})\s*days", txt, re.I)
    return int(m.group(1)) if m else None


def snapshot(rfq: dict, required_validity_days: int | None) -> dict:
    """Frozen copy of the approved RFQ (BRD flow step 2)."""
    return {"rfq_id": rfq["id"], "ref": rfq["ref"], "title": rfq["title"], "summary": rfq.get("summary", ""),
            "buyer_name": rfq.get("buyer_name"), "understanding": rfq.get("understanding"),
            "requirements": [{k: q.get(k) for k in ("id", "text", "type")} for q in rfq["requirements"]],
            "line_items": line_items(rfq),
            "required_validity_days": required_validity_days or required_validity(rfq),
            "has_docx": bool(rfq.get("template_id")), "frozen_at": now()}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def deadline_passed(deadline: str | None, at: datetime | None = None) -> bool:
    """Deadline is a date (YYYY-MM-DD); it is open until the end of that day (UTC)."""
    if not deadline:
        return False
    at = at or datetime.now(timezone.utc)
    try:
        d = datetime.fromisoformat(deadline[:10]).replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return at.date() > d.date()


def effective_status(q: dict, at: datetime | None = None) -> str:
    if q["status"] in ("sent", "viewed") and deadline_passed(q.get("deadline"), at):
        return "expired"
    return q["status"]


# ── quotation ────────────────────────────────────────────────────────────────
def blank_quotation(snap: dict, mode: str) -> dict:
    return {"mode": mode,
            "lines": [{**li, "unit_price": None} for li in snap["line_items"]],
            "gst_pct": 18, "freight": 0, "lead_time_days": None, "validity_days": None,
            "payment_terms": "", "payment_days": None, "min_order": None, "assumptions": "",
            "compliance": [{"req_id": r["id"], "text": r["text"], "response": "comply", "note": ""}
                           for r in snap["requirements"] if r["type"] == "mandatory"],
            "supporting": {"company": "", "certifications": [], "past_orders": []},
            "stated_total": None}


def _f(v) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def clean_quotation(q: dict, snap: dict) -> dict:
    """Normalise a quotation sent by the client / the AI; recompute totals."""
    base = blank_quotation(snap, q.get("mode") or "ai")
    out = {**base, **{k: q[k] for k in base if k in q}}
    out["lines"] = [{"desc": str(li.get("desc") or "").strip(), "qty": _f(li.get("qty")) or 0,
                     "unit": str(li.get("unit") or "units")[:20], "unit_price": _f(li.get("unit_price"))}
                    for li in (q.get("lines") or base["lines"]) if str(li.get("desc") or "").strip()]
    for k in ("gst_pct", "freight", "lead_time_days", "validity_days", "payment_days", "min_order", "stated_total"):
        out[k] = _f(out.get(k))
    out["gst_pct"] = 0 if out["gst_pct"] is None else out["gst_pct"]
    out["freight"] = 0 if out["freight"] is None else out["freight"]
    valid_req = {c["req_id"] for c in base["compliance"]}
    given = {c.get("req_id"): c for c in (q.get("compliance") or [])}
    out["compliance"] = [{**c, "response": "deviation" if (given.get(c["req_id"]) or {}).get("response") == "deviation"
                          else "comply", "note": str((given.get(c["req_id"]) or {}).get("note") or "")}
                         for c in base["compliance"] if c["req_id"] in valid_req]
    sup = q.get("supporting") or {}
    out["supporting"] = {"company": str(sup.get("company") or ""),
                         "certifications": [str(x) for x in (sup.get("certifications") or []) if x][:10],
                         "past_orders": [str(x) for x in (sup.get("past_orders") or []) if x][:10]}
    out["totals"] = compute_totals(out)
    return out


def compute_totals(q: dict) -> dict:
    sub = 0.0
    for li in q["lines"]:
        li["amount"] = round((li.get("qty") or 0) * li["unit_price"], 2) if li.get("unit_price") is not None else None
        sub += li["amount"] or 0
    tax = round(sub * (q.get("gst_pct") or 0) / 100, 2)
    fr = q.get("freight") or 0
    return {"subtotal": round(sub, 2), "tax": tax, "freight": fr, "landed_total": round(sub + tax + fr, 2)}


def pre_send_checks(q: dict, snap: dict, deadline: str | None = None) -> list[dict]:
    """[{level: error|warn, code, message}] — submit is blocked while any error remains."""
    out = []

    def add(level, code, msg):
        out.append({"level": level, "code": code, "message": msg})
    if not q["lines"]:
        add("error", "no_lines", "The quotation has no line items")
    for li in q["lines"]:
        if li.get("unit_price") in (None, 0) or li["unit_price"] < 0:
            add("error", "missing_price", f"Missing unit price for “{li['desc']}”")
        if not li.get("qty"):
            add("error", "missing_qty", f"Missing quantity for “{li['desc']}”")
    for c in q["compliance"]:
        if c["response"] == "deviation":
            add("error", "mandatory_deviation", f"Mandatory requirement marked as a deviation: “{c['text']}”")
    req = snap.get("required_validity_days")
    if q.get("validity_days") is None:
        add("warn" if not req else "error", "missing_validity", "Quote validity is not stated"
            + (f" (the RFQ asks for {req} days)" if req else ""))
    elif req and q["validity_days"] < req:
        add("error", "short_validity", f"Validity {q['validity_days']:g} days is shorter than the {req} days the RFQ asks")
    st = q.get("stated_total")
    if st is not None and abs(st - q["totals"]["landed_total"]) > max(1.0, 0.005 * st):
        add("error", "totals_mismatch", f"Stated total ₹{st:,.2f} does not match the calculated total "
                                        f"₹{q['totals']['landed_total']:,.2f}")
    if q.get("lead_time_days") is None:
        add("warn", "missing_lead_time", "Lead time is not stated")
    if not (q.get("payment_terms") or q.get("payment_days") is not None):
        add("warn", "missing_payment", "Payment terms are not stated")
    if deadline_passed(deadline):
        add("error", "deadline_passed", "The quote deadline has passed")
    return out


def has_errors(checks: list[dict]) -> bool:
    return any(c["level"] == "error" for c in checks)


# ── evaluation ───────────────────────────────────────────────────────────────
def validate_criteria(criteria: list[dict]) -> list[dict]:
    out = []
    for i, c in enumerate(criteria or [], 1):
        kind = c.get("kind")
        if kind not in ("numeric", "threshold", "descriptive"):
            raise ValueError(f"Criterion {i}: choose numeric, threshold or descriptive")
        name = str(c.get("name") or "").strip()
        if not name:
            raise ValueError(f"Criterion {i}: name is required")
        w = _f(c.get("weight"))
        if w is None or w < 0:
            raise ValueError(f"“{name}”: weight must be a positive number")
        x = {"id": f"c{i}", "name": name, "kind": kind, "weight": w,
             "description": str(c.get("description") or "").strip()}
        if kind in ("numeric", "threshold"):
            if c.get("field") not in FIELDS:
                raise ValueError(f"“{name}”: choose which quote value it is calculated from")
            x["field"] = c["field"]
            x["better"] = c.get("better") if c.get("better") in ("lower", "higher") else FIELDS[c["field"]]["better"]
        if kind == "threshold":
            lim = _f(c.get("limit"))
            if lim is None or lim <= 0:
                raise ValueError(f"“{name}”: set the limit")
            x["limit"] = lim
        if kind == "descriptive" and not x["description"]:
            raise ValueError(f"“{name}”: describe how the AI should judge it")
        out.append(x)
    if not out:
        raise ValueError("Add at least one criterion")
    total = sum(c["weight"] for c in out)
    if abs(total - 100) > 0.01:
        raise ValueError(f"Weights total {total:g}% — they must total 100%")
    return out


def quote_value(q: dict, field: str) -> float | None:
    return q["totals"]["landed_total"] if field == "landed_total" else q.get(field)


def score_rules(quotes: dict[str, dict], c: dict) -> dict[str, dict]:
    """quotes: {request_id: quotation}. Returns {request_id: {score, reason}} for one rule criterion."""
    label = FIELDS[c["field"]]["label"]
    vals = {k: quote_value(q, c["field"]) for k, q in quotes.items()}
    out = {}
    if c["kind"] == "numeric":
        present = [v for v in vals.values() if v is not None and v > 0]
        best = (min(present) if c["better"] == "lower" else max(present)) if present else None
        for k, v in vals.items():
            if v is None or v <= 0 or best is None:
                out[k] = {"score": 0.0, "reason": f"{label} not stated — scored 0"}
                continue
            s = 100 * (best / v if c["better"] == "lower" else v / best)
            out[k] = {"score": round(s, 1),
                      "reason": f"{label} {v:,.2f} vs best {best:,.2f} → {s:.1f}"
                      + (" (best)" if v == best else "")}
    else:  # threshold
        lim = c["limit"]
        for k, v in vals.items():
            if v is None:
                out[k] = {"score": 0.0, "reason": f"{label} not stated — scored 0"}
            elif (v <= lim) if c["better"] == "lower" else (v >= lim):
                out[k] = {"score": 100.0, "reason": f"{label} {v:g} meets the limit of {lim:g} → full score"}
            else:
                gap = (v - lim) if c["better"] == "lower" else (lim - v)
                s = max(0.0, 100 * (1 - gap / lim))
                out[k] = {"score": round(s, 1), "reason": f"{label} {v:g} misses the limit of {lim:g} by {gap:g} → {s:.1f}"}
    return out


def weighted(rows: dict[str, dict], criteria: list[dict]) -> list[tuple[str, float]]:
    """rows: {request_id: {criterion_id: {score}}} -> [(request_id, weighted_total)] best first."""
    tot = {k: round(sum(c["weight"] * (r.get(c["id"]) or {}).get("score", 0) / 100 for c in criteria), 1)
           for k, r in rows.items()}
    return sorted(tot.items(), key=lambda kv: (-kv[1], kv[0]))
