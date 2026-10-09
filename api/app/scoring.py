"""Pure gate + score. Same input -> same output; never calls the LLM.

- any mandatory requirement with status "not" -> rejected (with the failing requirements)
- otherwise full = 1, partial = 0.5, not / na = 0; category = mean of its requirements;
  total = equal-weight mean of the categories present (1/6 each when all six are present)
Requirements without catalog mapping are not scored.
"""
from __future__ import annotations

POINTS = {"full": 1.0, "partial": 0.5, "not": 0.0, "na": 0.0}


def req_category(req: dict, catalog_index: dict) -> str | None:
    for dp in req.get("data_point_ids") or []:
        if dp in catalog_index:
            return catalog_index[dp]["category"]
    return None


def score(requirements: list[dict], results: dict[str, dict], catalog_index: dict,
          categories: list[dict]) -> dict:
    failed, per_cat = [], {}
    for r in requirements:
        cat = req_category(r, catalog_index)
        if not cat:
            continue
        res = results.get(r["id"]) or {"status": "na", "reason": "Data not available"}
        if r["type"] == "mandatory" and res["status"] == "not":
            failed.append({"req_id": r["id"], "text": r["text"], "reason": res.get("reason", "")})
        per_cat.setdefault(cat, []).append(POINTS.get(res["status"], 0.0))

    cats = {c["id"]: {"label": c["label"], "score": round(sum(v) / len(v) * 100, 1), "n": len(v)}
            for c in categories if (v := per_cat.get(c["id"]))}
    total = round(sum(c["score"] for c in cats.values()) / len(cats), 1) if cats else 0.0
    counts = {k: sum(1 for r in requirements if req_category(r, catalog_index)
                     and (results.get(r["id"]) or {}).get("status", "na") == k) for k in POINTS}
    return {"status": "rejected" if failed else "ranked", "total": total, "categories": cats,
            "failed": failed, "counts": counts}
