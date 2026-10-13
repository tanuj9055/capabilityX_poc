"""The LLM parts of the PO: AI-assisted draft (narrative + clause selection) and uploaded-PO extraction.
Lines, prices and totals never come from the AI in the draft: po.clean re-copies them from the quotation."""
from __future__ import annotations

import json

from . import gemini, po, prompts, quotes


def draft(p: dict, req: dict, rfq: dict, seller: dict, profile: dict) -> dict:
    q = req["quotation"]
    lib = {t["id"]: t for t in profile.get("terms") or []}
    r = gemini.generate_json(prompts.DRAFT_PO.format(
        ref=rfq["ref"], title=rfq["title"],
        understanding=json.dumps(rfq.get("understanding") or {}, ensure_ascii=False),
        supplier=seller["name"], city=seller.get("city", ""), profile=seller.get("profile", ""),
        quote=json.dumps({k: q.get(k) for k in ("lines", "gst_pct", "freight", "totals", "lead_time_days",
                                                 "validity_days", "payment_terms", "payment_days", "min_order",
                                                 "assumptions", "compliance")}, ensure_ascii=False),
        buyer=json.dumps({k: profile.get(k) for k in ("name", "registered_office", "billing_address",
                                                       "shipping_addresses")}, ensure_ascii=False),
        terms="\n".join(f"{t['id']}: {t['title']} — {t['text']}" for t in lib.values()) or "(none saved)"),
        temperature=0, seed=7, tag=f"draft-po {req['id']}")
    if r.get("intro"):
        p["fields"]["intro"] = str(r["intro"])
    if r.get("po_type"):
        p["fields"]["po_type"] = str(r["po_type"])
    body = {k: r[k] for k in ("key_controls", "schedule", "clarifications") if isinstance(r.get(k), list)}
    ids = [i for i in r.get("term_ids") or [] if i in lib]  # selection only: unknown ids are dropped
    if ids:
        body["terms"] = [{k: lib[i][k] for k in ("id", "title", "text")} for i in ids]
    return po.clean(p, body, req)


def apply_answers(p: dict, answers: dict, req: dict) -> dict:
    fields = {k: str(v).strip() for k, v in (answers or {}).items() if k in po.TEXT_FIELDS and str(v or "").strip()}
    return po.clean(p, {"fields": fields}, req)


def extract(blocks: list[dict]) -> dict:
    r = gemini.generate_json(prompts.EXTRACT_PO.format(blocks="\n".join(f"[{b['id']}] {b['text']}" for b in blocks)),
                             temperature=0, seed=7, tag="extract-po")
    lines = []
    for li in r.get("lines") or []:
        if isinstance(li, dict) and li.get("desc"):
            unit = str(li.get("unit") or "units")
            lines.append({"desc": str(li["desc"]), "qty": li.get("qty") or (1 if unit.lower() == "lot" else 0),
                          "unit": unit, "unit_price": quotes._f(li.get("unit_price"))})
    fields = {k: str(r[k]) for k in po.TEXT_FIELDS if r.get(k) not in (None, "")}
    terms = [{"id": f"u{i}", "title": str(t.get("title") or ""), "text": str(t.get("text") or "")}
             for i, t in enumerate(r.get("terms") or [], 1) if isinstance(t, dict) and t.get("title")]
    return {"fields": fields, "lines": lines, "gst_pct": quotes._f(r.get("gst_pct")) or 0,
            "freight": quotes._f(r.get("freight")) or 0, "stated_total": quotes._f(r.get("stated_total")),
            "terms": terms}
