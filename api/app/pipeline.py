"""analyze_rfq (upload flow) -> gate (mandatory only) -> score (passing sellers) -> results.

Every MSME in the pool gets a gate result (BRD acceptance criterion 3); there is no relevance pre-filter.
Stage 1 (gate) checks only the mandatory requirements of every MSME; one that
fails one is rejected and never scored. Stage 2 evaluates the remaining (scored) requirements of
the sellers that passed; their gate results are kept, so the score covers all requirements.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor

from . import gemini, prompts, scoring, store

log = logging.getLogger("capabilityx.pipeline")
STATUSES = ("full", "partial", "not", "na")


# ── Flow A: uploaded RFQ -> requirements ─────────────────────────────────────
def analyze_rfq(blocks: list[dict]) -> dict:
    idx = store.catalog_index()
    cat_lines = "\n".join(f"{d['id']}: {d['label']} [{d['category']}]" for d in idx.values())
    block_txt = "\n".join(f"[{b['id']}] {b['text']}" for b in blocks)
    # no response_schema here: an 88-value enum inside a nested array made Gemini return
    # an empty list; ids are validated against the catalog below instead.
    r = gemini.generate_json(prompts.ANALYZE_RFQ.format(catalog=cat_lines, blocks=block_txt),
                             temperature=0, seed=7, tag="analyze")
    by_id = {b["id"]: b for b in blocks}
    reqs = []
    for q in r.get("requirements", []):
        dps = [d for d in q.get("data_point_ids", []) if d in idx][:3]
        src = [i for i in q.get("source_block_ids", []) if i in by_id]
        reqs.append({
            "id": f"r{len(reqs) + 1}", "text": q["text"].strip(),
            "type": q.get("type") if q.get("type") in ("mandatory", "scored") else "scored",
            "data_point_ids": dps, "source_block_ids": src,
            "source_quote": " … ".join(by_id[i]["text"] for i in src)[:400],
            "source": "upload",
        })
    return {"title": r.get("title") or "Uploaded RFQ", "buyer_name": r.get("buyer"),
            "summary": r.get("summary", ""), "item_category": r.get("item_category", ""),
            "understanding": _clean_understanding(r.get("understanding")), "requirements": reqs}


def _clean_understanding(u) -> dict:
    u = u if isinstance(u, dict) else {}
    out = {k: (str(u[k]).strip() if u.get(k) not in (None, "") else None) for k in (
        "item", "quantity", "contract_period", "delivery_location", "delivery_schedule",
        "payment_terms", "commercial_terms", "evaluation_basis")}
    out["key_dates"] = [{"label": str(x.get("label", "")), "date": str(x.get("date", ""))}
                        for x in (u.get("key_dates") or []) if isinstance(x, dict) and x.get("date")][:8]
    out["technical_specs"] = [{"label": str(x.get("label", "")), "value": str(x.get("value", ""))}
                              for x in (u.get("technical_specs") or []) if isinstance(x, dict) and x.get("value")][:8]
    out["documents_required"] = [str(x) for x in (u.get("documents_required") or []) if x][:8]
    return out


# ── background mapping (requirements the buyer added or reworded) ─────────────
def map_requirements(texts: list[str]) -> list[list[str]]:
    """One Gemini call: requirement texts -> catalog data point ids (validated)."""
    if not texts:
        return []
    idx = store.catalog_index()
    r = gemini.generate_json(prompts.MAP_REQUIREMENTS.format(
        catalog="\n".join(f"{d['id']}: {d['label']} [{d['category']}]" for d in idx.values()),
        requirements="\n".join(f"{i}. {t}" for i, t in enumerate(texts, 1))),
        temperature=0, seed=7, tag="map-requirements")
    by_n = {m.get("n"): m.get("data_point_ids") or [] for m in r.get("mappings", []) if isinstance(m, dict)}
    return [[d for d in by_n.get(i, []) if d in idx][:3] for i in range(1, len(texts) + 1)]


# ── match ────────────────────────────────────────────────────────────────────
def match_seller(rfq: dict, seller: dict, reqs: list[dict], stage: str = "match") -> dict[str, dict]:
    """Evaluate one seller on the given (mapped) requirements."""
    if not reqs:
        return {}
    idx = store.catalog_index()
    dps = sorted({d for r in reqs for d in r["data_point_ids"]})
    values = "\n".join(f"{d} ({idx[d]['label']}): {seller['values'].get(d) or 'null'}" for d in dps)
    req_txt = "\n".join(f"{r['id']} | {r['type']} | {r['text']} | {', '.join(r['data_point_ids'])}" for r in reqs)
    schema = {"type": "OBJECT", "properties": {"results": {"type": "ARRAY", "items": {
        "type": "OBJECT", "properties": {
            "req_id": {"type": "STRING"}, "status": {"type": "STRING", "enum": list(STATUSES)},
            "reason": {"type": "STRING"}}, "required": ["req_id", "status", "reason"]}}},
        "required": ["results"]}
    r = gemini.generate_json(prompts.MATCH.format(
        title=rfq["title"], summary=rfq.get("summary", ""), name=seller["name"], city=seller["city"],
        profile=seller["profile"], values=values, requirements=req_txt),
        temperature=0, seed=7, schema=schema, tag=f"{stage} {seller['id']}")
    ids = {q["id"] for q in reqs}
    out = {x["req_id"]: {"status": x["status"] if x.get("status") in STATUSES else "na",
                         "reason": x.get("reason", "")}
           for x in r.get("results", []) if x.get("req_id") in ids}
    for q in reqs:
        out.setdefault(q["id"], {"status": "na", "reason": "Data not available"})
    return out


def run_matching(rfq: dict) -> dict:
    """Stage 1 mandatory gate on every MSME -> stage 2 scoring of the MSMEs that passed.
    Cached in the RFQ: gate = stage-1 outcome per seller, matches = merged per-requirement results."""
    rfq.pop("shortlist", None)
    mapped = [r for r in rfq["requirements"] if r.get("data_point_ids")]
    mandatory = [r for r in mapped if r["type"] == "mandatory"]
    scored = [r for r in mapped if r["type"] != "mandatory"]
    targets = store.sellers()

    # stage 1: mandatory gate
    gate = dict(_parallel(rfq, targets, mandatory, "gate"))
    rfq["gate"] = {}
    passed = []
    for s in targets:
        g = gate.get(s["id"])
        if g is None:
            continue
        failed = [r["id"] for r in mandatory if g.get(r["id"], {}).get("status") == "not"]
        rfq["gate"][s["id"]] = {"passed": not failed, "failed": failed}
        if not failed:
            passed.append(s)

    # stage 2: score the sellers that passed on the remaining requirements
    stage2 = dict(_parallel(rfq, passed, scored, "score"))
    rfq["matches"] = {}
    for sid, g in gate.items():
        if g is None:
            continue
        if not rfq["gate"][sid]["passed"]:
            rfq["matches"][sid] = g
        elif stage2.get(sid) is not None:  # a failed scoring call shows as "matching failed"
            rfq["matches"][sid] = {**g, **stage2[sid]}
    return rfq


def _parallel(rfq, sellers, reqs, stage):
    def one(s):
        try:
            return s["id"], match_seller(rfq, s, reqs, stage)
        except Exception as e:  # one seller failing must not sink the run
            log.error("%s %s failed: %s", stage, s["id"], e)
            return s["id"], None
    if not sellers:
        return []
    with ThreadPoolExecutor(max_workers=10) as ex:
        return list(ex.map(one, sellers))


# ── results (pure) ───────────────────────────────────────────────────────────
def results(rfq: dict) -> dict:
    idx, cats = store.catalog_index(), store.catalog()["categories"]
    ranked, rejected, errors = [], [], []
    for s in store.sellers():
        base = {"seller_id": s["id"], "name": s["name"], "city": s["city"], "line": s.get("category_label")}
        m = rfq.get("matches", {}).get(s["id"])
        if m is None:
            errors.append({**base, "reason": "Matching failed — confirm again to retry"})
            continue
        sc = scoring.score(rfq["requirements"], m, idx, cats)
        (rejected if sc["status"] == "rejected" else ranked).append({**base, **sc})
    ranked.sort(key=lambda x: -x["total"])
    for i, x in enumerate(ranked, 1):
        x["rank"] = i
    return {"ranked": ranked, "rejected": rejected, "errors": errors,
            "categories": cats, "gate": gate_summary(rfq)}


def seller_detail(rfq: dict, sid: str) -> dict | None:
    s = store.seller(sid)
    m = (rfq.get("matches") or {}).get(sid)
    if not s or m is None:
        return None
    idx, cats = store.catalog_index(), store.catalog()["categories"]
    sc = scoring.score(rfq["requirements"], m, idx, cats)
    rows = []
    for r in rfq["requirements"]:
        cat = scoring.req_category(r, idx)
        if not cat:
            res = {"status": "unmapped", "reason": "Not covered by supplier data — not scored"}
        elif r["id"] in m:
            res = m[r["id"]]
        elif sc["status"] == "rejected":
            res = {"status": "skipped", "reason": "Not assessed — rejected at the mandatory gate"}
        else:
            res = {"status": "na", "reason": "Data not available"}
        rows.append({**r, "category": cat, **res,
                     "values": [{"id": d, "label": idx[d]["label"], "value": s["values"].get(d)}
                                for d in r.get("data_point_ids", [])]})
    return {"seller": {k: s[k] for k in ("id", "name", "city", "profile", "category_label")},
            "score": sc, "rows": rows, "categories": cats}


def gate_summary(rfq: dict) -> dict:
    g = rfq.get("gate") or {}
    return {"checked": len(g), "passed": sum(1 for x in g.values() if x["passed"]),
            "mandatory": sum(1 for r in rfq["requirements"] if r["type"] == "mandatory" and r.get("data_point_ids"))}


def dumps(o) -> str:
    return json.dumps(o, ensure_ascii=False)
