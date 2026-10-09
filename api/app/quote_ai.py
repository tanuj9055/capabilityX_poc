"""The LLM parts of quoting: AI-assisted draft, uploaded-quote extraction, descriptive scoring."""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor

from . import gemini, prompts, quotes, store

log = logging.getLogger("capabilityx.quotes")
# supporting-proof data points read from the seller profile
PROOF_DPS = ("legal_structure", "date_incorporation", "promoter_experience_yrs", "employees_permanent",
             "installed_capacity", "otd_pct", "rejection_rate_pct", "sector_certification", "iso_9001", "bis_cert",
             "client_reference", "top_customers", "approved_vendor_oems", "largest_order", "hsn_products", "turnover")


def _values(seller: dict, dps=PROOF_DPS) -> str:
    idx = store.catalog_index()
    return "\n".join(f"{idx[d]['label'] if d in idx else d}: {seller['values'].get(d)}"
                     for d in dps if seller["values"].get(d) not in (None, ""))


def _lines(snap: dict) -> str:
    return "\n".join(f"{li['desc']} | {li['qty']:g} | {li['unit']}" for li in snap["line_items"])


def _mandatory(snap: dict) -> str:
    return "\n".join(f"{r['id']}: {r['text']}" for r in snap["requirements"] if r["type"] == "mandatory") or "(none)"


def template(snap: dict, seller: dict) -> dict:
    """Standard quotation template (no AI): RFQ lines + the supplier's own recorded proof, prices left blank."""
    v = seller["values"]
    q = quotes.blank_quotation(snap, "template")
    q["supporting"] = {
        "company": f"{seller['name']}, {seller['city']} — {seller['profile']}",
        "certifications": [str(v[k]) for k in ("sector_certification", "iso_9001", "bis_cert") if v.get(k)],
        "past_orders": [f"{store.catalog_index().get(k, {}).get('label', k)}: {v[k]}"
                        for k in ("client_reference", "largest_order", "top_customers", "approved_vendor_oems")
                        if v.get(k) not in (None, "", "No")]}
    return quotes.clean_quotation(q, snap)


def draft(snap: dict, seller: dict) -> tuple[dict, list[dict]]:
    """AI-assisted draft -> (quotation, questions it cannot answer)."""
    r = gemini.generate_json(prompts.DRAFT_QUOTE.format(
        ref=snap["ref"], title=snap["title"], summary=snap.get("summary", ""),
        understanding=json.dumps(snap.get("understanding") or {}, ensure_ascii=False),
        lines=_lines(snap), mandatory=_mandatory(snap), name=seller["name"], city=seller["city"],
        profile=seller["profile"], values=_values(seller)), temperature=0, seed=7, tag=f"draft {seller['id']}")
    q = quotes.blank_quotation(snap, "ai")
    lines = [li for li in (r.get("lines") or []) if isinstance(li, dict) and li.get("desc")]
    if lines:
        q["lines"] = [{"desc": str(li["desc"]), "qty": li.get("qty") or 1, "unit": li.get("unit") or "units",
                       "unit_price": None} for li in lines]
    q["supporting"] = r.get("supporting") or q["supporting"]
    q["assumptions"] = str(r.get("assumptions_hint") or "")
    q = quotes.clean_quotation(q, snap)
    known = {"lead_time_days", "min_order", "validity_days", "payment_terms", "payment_days", "assumptions"}
    questions = []
    for x in r.get("questions") or []:
        qid = str((x or {}).get("id") or "")
        if (qid in known or qid.startswith("unit_price_")) and qid not in {y["id"] for y in questions}:
            questions.append({"id": qid, "question": str(x.get("question") or qid)})
    for i in range(1, len(q["lines"]) + 1):  # a price question per line is guaranteed
        if f"unit_price_{i}" not in {y["id"] for y in questions}:
            questions.insert(i - 1, {"id": f"unit_price_{i}", "question": f"Unit price (₹) for “{q['lines'][i - 1]['desc']}”?"})
    return q, questions


def apply_answers(q: dict, answers: dict) -> dict:
    for k, v in (answers or {}).items():
        if v in (None, ""):
            continue
        if k.startswith("unit_price_"):
            i = int(k.rsplit("_", 1)[1]) - 1
            if 0 <= i < len(q["lines"]):
                q["lines"][i]["unit_price"] = v
        elif k in ("lead_time_days", "min_order", "validity_days", "payment_days", "payment_terms", "assumptions"):
            q[k] = v
    if q.get("payment_days") in (None, "") and q.get("payment_terms"):  # "60 days credit" -> 60
        q["payment_days"] = quotes._num(q["payment_terms"])
    return q


def extract(blocks: list[dict], snap: dict) -> dict:
    """Uploaded quotation -> standard structure (the supplier confirms it in the editor)."""
    r = gemini.generate_json(prompts.EXTRACT_QUOTE.format(
        title=snap["title"], lines=_lines(snap).replace("\n", "; "), mandatory=_mandatory(snap),
        blocks="\n".join(f"[{b['id']}] {b['text']}" for b in blocks)), temperature=0, seed=7, tag="extract-quote")
    q = {**{k: r.get(k) for k in ("lines", "gst_pct", "freight", "lead_time_days", "validity_days",
                                  "payment_terms", "payment_days", "min_order", "assumptions", "stated_total",
                                  "supporting")}, "mode": "upload"}
    q["lines"] = [li for li in (q["lines"] or []) if isinstance(li, dict)] or None
    if q["gst_pct"] is None:
        q["gst_pct"] = 0  # not stated: the supplier sets it in the editor
    dev = {d.get("req_id"): d.get("note", "") for d in (r.get("deviations") or []) if isinstance(d, dict)}
    q["compliance"] = [{"req_id": rid, "response": "deviation", "note": note} for rid, note in dev.items()]
    if q.get("payment_days") is None and q.get("payment_terms"):
        q["payment_days"] = quotes._num(q["payment_terms"])
    return quotes.clean_quotation({k: v for k, v in q.items() if v is not None}, snap)


def score_descriptive(rfq: dict, reqs: list[dict], criteria: list[dict]) -> dict[str, dict]:
    """{request_id: {"scores": {criterion_id: {score, reason}}, risks, points_to_confirm}} — one call per quote.
    Always run (risks/points to confirm are wanted even with no descriptive criteria)."""
    desc = [c for c in criteria if c["kind"] == "descriptive"]
    crit_txt = "\n".join(f"{c['id']}: {c['name']} — {c['description']}" for c in desc) or "(none — return scores: [])"

    def one(q):
        s = store.seller(q["seller_id"])
        quote = {k: v for k, v in q["quotation"].items() if k not in ("mode",)}
        try:
            r = gemini.generate_json(prompts.SCORE_QUOTE.format(
                ref=rfq["ref"], title=rfq["title"], summary=rfq.get("summary", ""), name=s["name"], city=s["city"],
                profile=s["profile"], values=_values(s).replace("\n", "; "),
                quote=json.dumps(quote, ensure_ascii=False), criteria=crit_txt),
                temperature=0, seed=7, tag=f"score-quote {q['seller_id']}")
        except Exception as e:  # one quote failing must not sink the analysis
            log.error("score-quote %s failed: %s", q["id"], e)
            r = {}
        got = {x.get("criterion_id"): x for x in (r.get("scores") or []) if isinstance(x, dict)}
        scores = {}
        for c in desc:
            x = got.get(c["id"])
            if x is None:
                scores[c["id"]] = {"score": 0.0, "reason": "AI could not score this criterion — re-run the analysis"}
            else:
                scores[c["id"]] = {"score": max(0.0, min(100.0, float(x.get("score") or 0))),
                                   "reason": str(x.get("reason") or "")}
        return q["id"], {"scores": scores, "risks": [str(x) for x in (r.get("risks") or [])][:3],
                         "points_to_confirm": [str(x) for x in (r.get("points_to_confirm") or [])][:3]}
    if not reqs:
        return {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        return dict(ex.map(one, reqs))
