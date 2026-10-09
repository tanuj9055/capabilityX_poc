"""End-to-end check of the quotation module through the real API (in-process, real Gemini for AI steps).

Buyer builds a transformer RFQ from the template, confirms it, requests quotes from every supplier that
passed the gate; Remi quotes by template (first with a missing price + a mandatory deviation, which must
block sending), Transcore quotes with an AI draft, any third passer declines. Then the buyer runs the
evaluation twice (rule scores must be identical), reopens it, and accepts one quote.

    cd api && python tools/quote_e2e.py            # throwaway data dirs
    cd api && python tools/quote_e2e.py --keep     # write into the real data dirs (for a browser check)
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

if "--keep" not in sys.argv:
    tmp = Path(tempfile.mkdtemp(prefix="cx-quote-e2e-"))
    os.environ["RFQ_DIR"], os.environ["QUOTE_DIR"] = str(tmp / "rfqs"), str(tmp / "quotes")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

c = TestClient(app)
BUYER = {"X-Role": "buyer", "X-User-Id": "voltedge", "X-User-Name": "VoltEdge"}
OTHER_BUYER = {"X-Role": "buyer", "X-User-Id": "someone-else", "X-User-Name": "Someone"}
seller = lambda sid: {"X-Role": "seller", "X-User-Id": sid}  # noqa: E731
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        fails.append(name)


def ok(r):
    assert r.status_code == 200, f"{r.request.method} {r.request.url} -> {r.status_code} {r.text[:300]}"
    return r.json()


# ── buyer: RFQ -> results -> quote requests ──────────────────────────────────
r = ok(c.post("/api/rfqs/from-template", json={"template_id": "transformer"}, headers=BUYER))
rid = r["id"]
ok(c.put(f"/api/rfqs/{rid}/slots", json={"values": {"buyer": "VoltEdge Power Pvt Ltd", "quantity": 50,
                                                    "standard": "IS 2026"}}, headers=BUYER))
ok(c.post(f"/api/rfqs/{rid}/approve", headers=BUYER))
ok(c.post(f"/api/rfqs/{rid}/confirm", headers=BUYER))
res = ok(c.get(f"/api/rfqs/{rid}/results", headers=BUYER))
rfq = ok(c.get(f"/api/rfqs/{rid}", headers=BUYER))
passed = [sid for sid, g in (rfq.get("gate") or {}).items() if g.get("passed")]
failed = [sid for sid, g in (rfq.get("gate") or {}).items() if not g.get("passed")]
print(f"RFQ {rfq['ref']} — gate passed: {passed}, failed: {failed}")
check("Remi and Transcore pass the transformer gate", {"ref-remi", "ref-transcore"} <= set(passed), passed)

deadline = (date.today() + timedelta(days=7)).isoformat()
if failed:
    x = c.post(f"/api/rfqs/{rid}/quote-requests", json={"seller_ids": failed[:1], "deadline": deadline}, headers=BUYER)
    check("C1 cannot request a quote from a gate-failed supplier", x.status_code == 400, x.status_code)
x = c.post(f"/api/rfqs/{rid}/quote-requests", json={"seller_ids": passed, "deadline": "2000-01-01"}, headers=BUYER)
check("C1 past deadline refused", x.status_code == 400, x.status_code)
sent = ok(c.post(f"/api/rfqs/{rid}/quote-requests",
                 json={"seller_ids": passed, "deadline": deadline, "required_validity_days": 90}, headers=BUYER))
check("C1 quote requests sent to all gate-passed suppliers", sorted(sent["sent"]) == sorted(passed))
again = ok(c.post(f"/api/rfqs/{rid}/quote-requests", json={"seller_ids": passed, "deadline": deadline}, headers=BUYER))
check("C1 re-sending is idempotent", again["sent"] == [] and len(again["requests"]) == len(passed))
req_of = {q["seller_id"]: q["id"] for q in sent["requests"]}

# ── sellers ──────────────────────────────────────────────────────────────────
lst = ok(c.get("/api/seller/requests", headers=seller("ref-remi")))
check("C2 seller sees the request with RFQ + buyer + deadline",
      any(q["id"] == req_of["ref-remi"] and q["buyer_name"] and q["deadline"] == deadline and q["rfq"]["title"]
          for q in lst))
remi_q = req_of["ref-remi"]
q = ok(c.get(f"/api/seller/requests/{remi_q}", headers=seller("ref-remi")))
check("C2 first open marks Viewed", q["status"] == "viewed" and q["viewed_at"])
check("C2 seller gets the tender understanding + own fit", bool(q["rfq"]["understanding"]) and bool(q.get("fit")))
check("C4 seller payload carries no evaluation / other requests",
      not any(k in q for k in ("evaluation", "requests", "gate", "matches")))

x = c.get(f"/api/seller/requests/{remi_q}", headers=seller("ref-transcore"))
check("C4 another supplier cannot open Remi's request", x.status_code == 404, x.status_code)
x = c.get(f"/api/rfqs/{rid}/quotes", headers=OTHER_BUYER)
check("C4 another buyer cannot see this RFQ's quotes", x.status_code == 404, x.status_code)
x = c.get(f"/api/rfqs/{rid}/quotes", headers=seller("ref-remi"))
check("C4 a supplier cannot call buyer routes", x.status_code in (401, 403), x.status_code)

# Remi: template mode, first with errors
q = ok(c.post(f"/api/seller/requests/{remi_q}/draft", json={"mode": "template"}, headers=seller("ref-remi")))
d = q["draft"]
check("C3 template draft has RFQ lines", len(d["lines"]) >= 1)
bad = {**d, "lines": [{**li, "unit_price": None} for li in d["lines"]], "validity_days": 30,
       "compliance": [{**cc, "response": "deviation"} if i == 0 else cc for i, cc in enumerate(d["compliance"])]}
q = ok(c.put(f"/api/seller/requests/{remi_q}/quotation", json={"quotation": bad}, headers=seller("ref-remi")))
codes = {x["code"] for x in q["checks"] if x["level"] == "error"}
check("C3 missing price flagged", "missing_price" in codes, codes)
if d["compliance"]:
    check("C3 mandatory deviation flagged", "mandatory_deviation" in codes, codes)
check("C3 validity shorter than RFQ's 90 days flagged", "short_validity" in codes, codes)
x = c.post(f"/api/seller/requests/{remi_q}/submit", headers=seller("ref-remi"))
check("C3 submit blocked while errors remain", x.status_code == 400, x.status_code)
good = {**d, "lines": [{**li, "unit_price": 410000} for li in d["lines"]], "gst_pct": 18, "freight": 75000,
        "lead_time_days": 45, "validity_days": 90, "payment_days": 30, "payment_terms": "100% within 30 days of delivery"}
q = ok(c.put(f"/api/seller/requests/{remi_q}/quotation", json={"quotation": good}, headers=seller("ref-remi")))
check("C3 totals calculated by rule", abs(q["draft"]["totals"]["landed_total"]
                                          - (sum(li["qty"] for li in d["lines"]) * 410000 * 1.18 + 75000)) < 1)
q = ok(c.post(f"/api/seller/requests/{remi_q}/submit", headers=seller("ref-remi")))
check("C5 Remi quotation sent", q["status"] == "quoted" and q["revision"] == 1)
good["lead_time_days"] = 40
ok(c.put(f"/api/seller/requests/{remi_q}/quotation", json={"quotation": good}, headers=seller("ref-remi")))
q = ok(c.post(f"/api/seller/requests/{remi_q}/submit", headers=seller("ref-remi")))
check("C5 revision before deadline allowed", q["revision"] == 2 and q["quotation"]["lead_time_days"] == 40)

# Transcore: AI-assisted draft
tq = req_of["ref-transcore"]
ok(c.get(f"/api/seller/requests/{tq}", headers=seller("ref-transcore")))
q = ok(c.post(f"/api/seller/requests/{tq}/draft", json={"mode": "ai"}, headers=seller("ref-transcore")))
print("   AI questions:", [x["id"] for x in q["questions"]])
print("   AI supporting:", q["draft"]["supporting"])
check("C6 AI draft asks what it can't know", len(q["questions"]) > 0)
check("C6 AI draft fills supporting proof from the profile",
      bool(q["draft"]["supporting"]["certifications"] or q["draft"]["supporting"]["past_orders"]))
check("C6 AI draft leaves unit prices empty (not invented)", all(li["unit_price"] in (None, 0) for li in q["draft"]["lines"]))
ans = {x["id"]: "" for x in q["questions"]}
for k in ans:
    ans[k] = "395000" if k.startswith("unit_price_") else { "lead_time_days": "60", "validity_days": "120", "payment_days": "45",
              "payment_terms": "30% advance, balance 45 days after delivery", "min_order": "10",
              "assumptions": "CRGO steel price as of this week"}.get(k, "")
q = ok(c.post(f"/api/seller/requests/{tq}/ai-answers", json={"answers": ans}, headers=seller("ref-transcore")))
print("   after answers:", {k: q["draft"].get(k) for k in ("lead_time_days", "validity_days", "payment_days")},
      [li["unit_price"] for li in q["draft"]["lines"]], [x["code"] for x in q["checks"]])
if any(x["level"] == "error" for x in q["checks"]):  # fill anything the mapping missed, as a seller would
    dd = q["draft"]
    dd = {**dd, "lines": [{**li, "unit_price": li["unit_price"] or 395000} for li in dd["lines"]],
          "validity_days": dd.get("validity_days") or 120, "gst_pct": 18}
    q = ok(c.put(f"/api/seller/requests/{tq}/quotation", json={"quotation": dd}, headers=seller("ref-transcore")))
q = ok(c.post(f"/api/seller/requests/{tq}/submit", headers=seller("ref-transcore")))
check("C5 Transcore AI-assisted quotation sent", q["status"] == "quoted")

# third passer (if any) declines; one more stays untouched
others = [s for s in passed if s not in ("ref-remi", "ref-transcore")]
if others:
    x = c.post(f"/api/seller/requests/{req_of[others[0]]}/decline", json={"reason": ""}, headers=seller(others[0]))
    check("C7 decline needs a reason", x.status_code == 400, x.status_code)
    q = ok(c.post(f"/api/seller/requests/{req_of[others[0]]}/decline", json={"reason": "Capacity full this quarter"},
                  headers=seller(others[0])))
    check("C7 decline recorded", q["status"] == "declined")

else:  # only two suppliers pass this gate: exercise decline on a second RFQ
    r2 = ok(c.post("/api/rfqs/from-template", json={"template_id": "transformer"}, headers=BUYER))["id"]
    ok(c.put(f"/api/rfqs/{r2}/slots", json={"values": {"buyer": "VoltEdge Power Pvt Ltd", "quantity": 5,
                                                       "standard": "IEC 60076"}}, headers=BUYER))
    ok(c.post(f"/api/rfqs/{r2}/approve", headers=BUYER))
    ok(c.post(f"/api/rfqs/{r2}/confirm", headers=BUYER))
    d2 = ok(c.post(f"/api/rfqs/{r2}/quote-requests", json={"seller_ids": ["ref-remi"], "deadline": deadline},
                   headers=BUYER))["requests"][0]["id"]
    x = c.post(f"/api/seller/requests/{d2}/decline", json={"reason": ""}, headers=seller("ref-remi"))
    check("C7 decline needs a reason", x.status_code == 400, x.status_code)
    q = ok(c.post(f"/api/seller/requests/{d2}/decline", json={"reason": "Capacity full this quarter"},
                  headers=seller("ref-remi")))
    check("C7 decline recorded", q["status"] == "declined" and not q["open"])
    t2 = ok(c.get(f"/api/rfqs/{r2}/quotes", headers=BUYER))["requests"][0]
    check("C7 buyer sees the decline + reason", t2["status"] == "declined" and t2["decline_reason"])
    x = c.post(f"/api/seller/requests/{d2}/draft", json={"mode": "template"}, headers=seller("ref-remi"))
    check("C7 cannot quote after declining", x.status_code == 409, x.status_code)

    # upload mode: Transcore uploads its own quotation; the stated total is wrong on purpose
    ok(c.post(f"/api/rfqs/{r2}/quote-requests", json={"seller_ids": ["ref-transcore"], "deadline": deadline},
              headers=BUYER))
    u2 = next(q["id"] for q in ok(c.get("/api/seller/requests", headers=seller("ref-transcore")))
              if q["rfq"]["ref"] == ok(c.get(f"/api/rfqs/{r2}", headers=BUYER))["ref"])
    doc = ("QUOTATION - Transcore, Bhopal\nItem: Distribution transformer as per RFQ, Qty 5 Nos\n"
           "Unit rate Rs 4,00,000 per No.\nGST @ 18% extra\nFreight: Rs 20,000 lump sum\n"
           "Delivery: 50 days from PO\nValidity: 90 days\nPayment: 100% within 30 days of delivery\n"
           "Grand total: Rs 25,00,000\n")
    q = ok(c.post(f"/api/seller/requests/{u2}/upload", files={"file": ("transcore_quote.txt", doc.encode(), "text/plain")},
                  headers=seller("ref-transcore")))
    dd = q["draft"]
    print("   upload extracted:", [(li["qty"], li["unit_price"]) for li in dd["lines"]], dd["gst_pct"], dd["freight"],
          dd["lead_time_days"], dd["validity_days"], dd["payment_days"], dd["stated_total"], dd["totals"]["landed_total"])
    check("C6 upload extracted into the standard structure", dd["mode"] == "upload" and dd["lines"]
          and dd["lines"][0]["unit_price"] == 400000 and dd["lead_time_days"] == 50)
    check("C3 stated total != calculated total flagged", "totals_mismatch" in {x["code"] for x in q["checks"]},
          [x["code"] for x in q["checks"]])
    q = ok(c.put(f"/api/seller/requests/{u2}/quotation", json={"quotation": {**dd, "stated_total": dd["totals"]["landed_total"]}},
                 headers=seller("ref-transcore")))
    q = ok(c.post(f"/api/seller/requests/{u2}/submit", headers=seller("ref-transcore")))
    check("C5 uploaded quotation sent after correction", q["status"] == "quoted")

# ── buyer: tracker, evaluation, accept ───────────────────────────────────────
qs = ok(c.get(f"/api/rfqs/{rid}/quotes", headers=BUYER))
st = {x["seller_id"]: x["status"] for x in qs["requests"]}
print("   tracker:", st)
check("C8 tracker shows each supplier's status", st["ref-remi"] == "quoted" and st["ref-transcore"] == "quoted"
      and all(st[s] == "declined" for s in others[:1]))
lst = ok(c.get("/api/quote-eval", headers=BUYER))
check("C8 Quote Evaluation list counts", any(x["id"] == rid and x["counts"]["quoted"] == 2 for x in lst))

bad_c = [{**cc, "weight": 10} for cc in qs["default_criteria"]]
x = c.post(f"/api/rfqs/{rid}/evaluation/run", json={"criteria": bad_c}, headers=BUYER)
check("C9 weights must total 100", x.status_code == 400, x.status_code)
crit = qs["default_criteria"]
e1 = ok(c.post(f"/api/rfqs/{rid}/evaluation/run", json={"criteria": crit}, headers=BUYER))
e2 = ok(c.post(f"/api/rfqs/{rid}/evaluation/run", json={"criteria": crit}, headers=BUYER))
rule_ids = [cc["id"] for cc in e1["criteria"] if cc["kind"] != "descriptive"]
rules = lambda e: {x["request_id"]: {k: x["scores"][k] for k in rule_ids} for x in e["results"]}  # noqa: E731
check("C10 numeric/threshold scores identical across runs", rules(e1) == rules(e2))
for x in e2["results"]:
    print(f"   #{x['rank']} {x['seller_name']}: {x['total']}  "
          + "  ".join(f"{k}={v['score']}" for k, v in x["scores"].items()))
desc_ids = [cc["id"] for cc in e1["criteria"] if cc["kind"] == "descriptive"]
check("C11 descriptive criteria scored by AI with a reason",
      all(x["scores"][k]["reason"] and "could not" not in x["scores"][k]["reason"] for x in e2["results"] for k in desc_ids))
check("C11 risks / points to confirm present", all(x["risks"] or x["points_to_confirm"] for x in e2["results"]))
check("C10 lowest landed price ranks best on price",
      max(e2["results"], key=lambda x: x["scores"]["c1"]["score"])["landed_total"]
      == min(x["landed_total"] for x in e2["results"]))
g = ok(c.get(f"/api/rfqs/{rid}/evaluation", headers=BUYER))
check("C10 reopening shows the saved analysis unchanged", g == e2)

top = e2["results"][0]["request_id"]
r = ok(c.post(f"/api/rfqs/{rid}/quotes/{top}/accept", headers=BUYER))
oc = {x["id"]: x["outcome"] for x in r["requests"] if x["status"] == "quoted"}
check("C12 accepted / not selected recorded", oc[top] == "accepted"
      and all(v == "not_selected" for k, v in oc.items() if k != top))
x = c.post(f"/api/rfqs/{rid}/quotes/{top}/accept", headers=BUYER)
check("C12 only one quote can be accepted", x.status_code == 409, x.status_code)
loser = next(k for k in oc if k != top)
loser_sid = next(s for s, q in req_of.items() if q == loser)
v = ok(c.get(f"/api/seller/requests/{loser}", headers=seller(loser_sid)))
check("C12 supplier sees the outcome and can no longer edit", v["outcome"] == "not_selected" and not v["open"])
x = c.post(f"/api/seller/requests/{loser}/submit", headers=seller(loser_sid))
check("C12 edits refused after the decision", x.status_code == 409, x.status_code)

print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAILED: ' + '; '.join(fails)}  (RFQ {rid})")
sys.exit(1 if fails else 0)
