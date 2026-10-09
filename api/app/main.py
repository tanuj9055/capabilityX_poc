"""CapabilityX POC — FastAPI routes + static SPA.

Demo sign-in (no password): the client sends X-Role (buyer|seller) and X-User-Id. A buyer id is a slug of
the company name typed at sign-in; a seller id is one of the MSMEs in sellers.json. A buyer sees only the
RFQs it created (prototype BRD criterion 5); a seller sees only its own quote requests (quotation BRD
criterion 4). Anything else gets 404.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path
from urllib.parse import unquote

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import Body, Depends, FastAPI, File, Header, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from . import ingest, pipeline, quote_ai, quotes, rfq_builder, store  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = FastAPI(title="CapabilityX POC")


# ── helpers ──────────────────────────────────────────────────────────────────
def _session(x_role: str | None = Header(None), x_user_id: str | None = Header(None),
             x_user_name: str | None = Header(None)) -> dict:
    return {"role": x_role, "id": x_user_id, "name": x_user_name}


def _user(role: str, h: dict) -> dict:
    uid = (h.get("id") or "").strip()
    if h.get("role") != role:
        raise HTTPException(403 if h.get("role") in ("buyer", "seller") else 401,
                            f"Sign in as a {role}" if h.get("role") else "Not signed in")
    if role == "buyer":
        if not re.fullmatch(r"[A-Za-z0-9-]{2,64}", uid):
            raise HTTPException(401, "Not signed in")
        return {"id": uid, "name": unquote(h.get("name") or "").strip()[:80] or uid}
    s = store.seller(uid)
    if not s:
        raise HTTPException(401, "Unknown supplier")
    return {"id": uid, "name": s["name"]}


def _buyer(h: dict) -> dict:
    return _user("buyer", h)


def _rfq(rid: str, h: dict) -> dict:
    u = _buyer(h)
    r = store.load_rfq(rid)
    if not r or r["buyer_id"] != u["id"]:
        raise HTTPException(404, "RFQ not found")
    return r


def _view(r: dict) -> dict:
    """RFQ as returned to the client (adds template info + live preview for drafts)."""
    out = {k: v for k, v in r.items() if k not in ("blocks",)}
    if r.get("template_id"):
        t = rfq_builder.template(r["template_id"])
        out["template"] = rfq_builder.template_public(t)
        out["effective"] = rfq_builder.effective(r)
        out["missing"] = [s["id"] for s in rfq_builder.missing_required(r)]
        out["preview"] = rfq_builder.render_blocks(r)
    out["has_docx"] = bool(r.get("template_id")) and r["status"] != "draft"
    return out


def _new_rfq(u: dict, mode: str, **kw) -> dict:
    rid = store.new_id()
    return {"id": rid, "buyer_id": u["id"], "buyer_display": u["name"], "mode": mode, "status": "draft", "created_at": store.now(),
            "ref": f"RFQ-{store.now()[:4]}-{rid[:5].upper()}", "title": "", "summary": "",
            "slots": {}, "messages": [], "requirements": [], **kw}


# ── static data ──────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/catalog")
def catalog():
    return store.catalog()


@app.get("/api/templates")
def list_templates():
    return [rfq_builder.template_public(t) for t in rfq_builder.templates().values()]


@app.get("/api/sellers")
def list_sellers():
    return [{k: s[k] for k in ("id", "name", "city", "category", "category_label", "profile")}
            for s in store.sellers()]


# ── RFQs ─────────────────────────────────────────────────────────────────────
@app.get("/api/rfqs")
def my_rfqs(h: dict = Depends(_session)):
    u = _buyer(h)
    return [{k: r.get(k) for k in ("id", "ref", "title", "mode", "status", "created_at", "updated_at")}
            for r in store.list_rfqs(u["id"])]


@app.get("/api/rfqs/{rid}")
def get_rfq(rid: str, h: dict = Depends(_session)):
    return _view(_rfq(rid, h))


@app.delete("/api/rfqs/{rid}")
def delete_rfq(rid: str, h: dict = Depends(_session)):
    r = _rfq(rid, h)
    for ext in ("json", "docx"):
        store.rfq_path(r["id"], ext).unlink(missing_ok=True)
    for q in store.list_requests(rfq_id=r["id"]):  # withdraw its quote requests too
        for ext in ("json", "docx"):
            store.request_path(q["id"], ext).unlink(missing_ok=True)
    return {"ok": True}


# Flow B: chat
@app.post("/api/rfqs/chat")
def chat_start(body: dict = Body(...), h: dict = Depends(_session)):
    u = _buyer(h)
    msg = (body.get("message") or "").strip()
    if not msg:
        raise HTTPException(400, "Describe what you need")
    tid, reason = rfq_builder.select_template(msg)
    r = _new_rfq(u, "chat", template_id=tid, template_reason=reason)
    rfq_builder.chat_turn(r, msg, None)
    r["title"] = r["slots"].get("rfq_title") or rfq_builder.template(tid)["name"]
    return _view(store.save_rfq(r))


@app.post("/api/rfqs/{rid}/chat")
def chat(rid: str, body: dict = Body(...), h: dict = Depends(_session)):
    r = _rfq(rid, h)
    if r["status"] != "draft":
        raise HTTPException(409, "RFQ already approved")
    rfq_builder.chat_turn(r, body.get("message"), body.get("values"))
    r["title"] = r["slots"].get("rfq_title") or r["title"]
    return _view(store.save_rfq(r))


# Flow C: template form
@app.post("/api/rfqs/from-template")
def from_template(body: dict = Body(...), h: dict = Depends(_session)):
    u = _buyer(h)
    tid = body.get("template_id")
    if tid not in rfq_builder.templates():
        raise HTTPException(400, "Unknown template")
    r = _new_rfq(u, "form", template_id=tid, title=rfq_builder.template(tid)["name"])
    return _view(store.save_rfq(r))


@app.put("/api/rfqs/{rid}/slots")
def set_slots(rid: str, body: dict = Body(...), h: dict = Depends(_session)):
    r = _rfq(rid, h)
    if r["status"] != "draft":
        raise HTTPException(409, "RFQ already approved")
    t = rfq_builder.template(r["template_id"])
    for sid, v in (body.get("values") or {}).items():
        if sid in t["slot_index"] and v in (None, "", []):
            r["slots"].pop(sid, None)
    rfq_builder.apply_values(r, body.get("values") or {})
    r["title"] = r["slots"].get("rfq_title") or r["title"]
    return _view(store.save_rfq(r))


@app.post("/api/rfqs/{rid}/approve")
def approve(rid: str, h: dict = Depends(_session)):
    r = _rfq(rid, h)
    if r["status"] != "draft":
        raise HTTPException(409, "RFQ already approved")
    miss = rfq_builder.missing_required(r)
    if miss:
        raise HTTPException(400, "Missing: " + ", ".join(s["label"] for s in miss))
    vals = rfq_builder.effective(r)
    r["title"] = vals.get("rfq_title") or r["title"]
    r["summary"] = (f"{vals.get('rfq_title')}: {rfq_builder.display({'type': 'number'}, vals.get('quantity'))} units over "
                    f"{vals.get('schedule_months')} months, {vals.get('delivery_model')} to "
                    f"{vals.get('delivery_location')}, payment {vals.get('payment_days')} days. "
                    f"Template: {rfq_builder.template(r['template_id'])['name']}.")
    r["requirements"] = rfq_builder.requirements_from_slots(r)
    r["understanding"] = rfq_builder.understanding_from_slots(r)
    rfq_builder.render_docx(r)
    r["status"] = "review"
    return _view(store.save_rfq(r))


@app.get("/api/rfqs/{rid}/docx")
def download_docx(rid: str, role: str | None = None, uid: str | None = None,
                  h: dict = Depends(_session)):
    r = _rfq(rid, {**h, "role": h["role"] or role, "id": h["id"] or uid})  # ?role=&uid= for a plain <a href>
    if not r.get("template_id"):
        raise HTTPException(404, "No generated document for an uploaded RFQ")
    p = store.rfq_path(r["id"], "docx")
    if not p.exists():
        rfq_builder.render_docx(r)
    name = "".join(c if c.isalnum() else "_" for c in (r.get("title") or "RFQ"))[:60]
    return FileResponse(p, filename=f"{r['ref']}_{name}.docx",
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


# Flow A: upload
@app.post("/api/rfqs/upload")
async def upload(file: UploadFile = File(...), h: dict = Depends(_session)):
    u = _buyer(h)
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "File too large (20 MB max)")
    try:
        blocks = ingest.to_blocks(data, file.filename or "upload")
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not blocks:
        raise HTTPException(400, "No text found in the document")
    a = pipeline.analyze_rfq(blocks)
    r = _new_rfq(u, "upload", filename=file.filename, blocks=blocks, title=a["title"],
                 summary=a["summary"], item_category=a["item_category"], buyer_name=a["buyer_name"],
                 understanding=a["understanding"],
                 requirements=a["requirements"], status="review")
    return _view(store.save_rfq(r))


# Review -> confirm -> results
@app.put("/api/rfqs/{rid}/requirements")
def set_requirements(rid: str, body: dict = Body(...), h: dict = Depends(_session)):
    r = _rfq(rid, h)
    if r["status"] != "review":
        raise HTTPException(409, "Requirements are frozen")
    idx = store.catalog_index()
    before = {q["id"]: q for q in r["requirements"]}
    clean, used, remap = [], set(), []
    for q in body.get("requirements") or []:
        text = str(q.get("text") or "").strip()
        if not text:
            continue
        qid, n = q.get("id"), len(clean)
        while not qid or qid in used:
            n += 1
            qid = f"r{n}n"
        used.add(qid)
        clean.append({**{k: q[k] for k in ("source_quote", "source_block_ids", "source") if k in q},
                      "id": qid, "text": text,
                      "type": "mandatory" if q.get("type") == "mandatory" else "scored",
                      "data_point_ids": [d for d in (q.get("data_point_ids") or []) if d in idx][:3]})
        old = before.get(q.get("id"))
        if not old or old["text"] != text:  # new or reworded -> map to data points in the background
            remap.append(clean[-1])
    for q, dps in zip(remap, pipeline.map_requirements([q["text"] for q in remap])):
        q["data_point_ids"] = dps
    r["requirements"] = clean
    return _view(store.save_rfq(r))


@app.post("/api/rfqs/{rid}/confirm")
def confirm(rid: str, h: dict = Depends(_session)):
    r = _rfq(rid, h)
    if r["status"] not in ("review", "results"):
        raise HTTPException(409, "Approve the RFQ first")
    if not any(q.get("data_point_ids") for q in r["requirements"]):
        raise HTTPException(400, "No requirement is mapped to supplier data")
    r["status"] = "results"
    r["confirmed_at"] = store.now()
    pipeline.run_matching(r)
    return _view(store.save_rfq(r))


@app.get("/api/rfqs/{rid}/results")
def results(rid: str, h: dict = Depends(_session)):
    r = _rfq(rid, h)
    if r["status"] != "results":
        raise HTTPException(409, "Not matched yet")
    return pipeline.results(r)


@app.get("/api/rfqs/{rid}/sellers/{sid}")
def seller_detail(rid: str, sid: str, h: dict = Depends(_session)):
    d = pipeline.seller_detail(_rfq(rid, h), sid)
    if not d:
        raise HTTPException(404, "Seller was not matched for this RFQ")
    return d


# ── Quote requests: buyer side ───────────────────────────────────────────────
def _buyer_request_view(q: dict) -> dict:
    out = {k: q.get(k) for k in ("id", "seller_id", "seller_name", "deadline", "sent_at", "viewed_at",
                                 "submitted_at", "decline_reason", "revision", "outcome")}
    out["status"] = quotes.effective_status(q)
    if q["status"] == "quoted":
        out["quotation"] = q["quotation"]
        out["checks"] = q.get("checks", [])
    return out


def _issuer(r: dict) -> str:
    name = r.get("buyer_name")
    if not name and r.get("template_id"):
        name = rfq_builder.effective(r).get("buyer")
    return name or r.get("buyer_display") or r["buyer_id"]


@app.post("/api/rfqs/{rid}/quote-requests")
def request_quotes(rid: str, body: dict = Body(...), h: dict = Depends(_session)):
    r = _rfq(rid, h)
    if r["status"] != "results":
        raise HTTPException(409, "Match suppliers first")
    deadline = str(body.get("deadline") or "")[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", deadline) or quotes.deadline_passed(deadline):
        raise HTTPException(400, "Choose a deadline from today onwards")
    validity = str(body.get("required_validity_days") or "")
    validity = int(validity) if validity.isdigit() and int(validity) > 0 else None
    ids = [i for i in (body.get("seller_ids") or []) if isinstance(i, str)]
    if not ids:
        raise HTTPException(400, "Select at least one supplier")
    gate = r.get("gate") or {}
    if any(not (gate.get(i) or {}).get("passed") for i in ids):
        raise HTTPException(400, "Only suppliers that passed the mandatory gate can be asked for a quote")
    existing = {q["seller_id"] for q in store.list_requests(rfq_id=r["id"])}
    snap = quotes.snapshot(r, validity)
    sent = []
    for sid in ids:
        if sid in existing:  # idempotent per supplier
            continue
        q = {"id": store.new_id(), "rfq_id": r["id"], "buyer_id": r["buyer_id"], "buyer_name": _issuer(r),
             "seller_id": sid, "seller_name": store.seller(sid)["name"], "deadline": deadline, "status": "sent",
             "sent_at": store.now(), "viewed_at": None, "rfq": snap,
             "fit": pipeline.seller_detail(r, sid), "decline_reason": None, "quotation": None,
             "draft": None, "questions": [], "checks": [], "revision": 0, "submitted_at": None, "outcome": None}
        if snap["has_docx"] and store.rfq_path(r["id"], "docx").exists():  # frozen copy of the document
            shutil.copyfile(store.rfq_path(r["id"], "docx"), store.request_path(q["id"], "docx"))
        store.save_request(q)
        sent.append(sid)
    return {"sent": sent, "requests": [_buyer_request_view(q) for q in store.list_requests(rfq_id=r["id"])]}


@app.get("/api/rfqs/{rid}/quotes")
def rfq_quotes(rid: str, h: dict = Depends(_session)):
    r = _rfq(rid, h)
    return {"rfq": {k: r.get(k) for k in ("id", "ref", "title", "summary", "status")},
            "requests": [_buyer_request_view(q) for q in store.list_requests(rfq_id=r["id"])],
            "evaluation": r.get("evaluation"), "default_criteria": quotes.DEFAULT_CRITERIA,
            "fields": quotes.FIELDS}


@app.get("/api/quote-eval")
def quote_eval_list(h: dict = Depends(_session)):
    u = _buyer(h)
    out = []
    for r in store.list_rfqs(u["id"]):
        reqs = store.list_requests(rfq_id=r["id"])
        if not reqs:
            continue
        counts = {k: 0 for k in quotes.STATUSES}
        for q in reqs:
            counts[quotes.effective_status(q)] += 1
        out.append({"id": r["id"], "ref": r["ref"], "title": r["title"], "requests": len(reqs), "counts": counts,
                    "deadline": max(q["deadline"] for q in reqs), "evaluated": bool(r.get("evaluation")),
                    "accepted": next((q["seller_name"] for q in reqs if q.get("outcome") == "accepted"), None)})
    return out


@app.post("/api/rfqs/{rid}/evaluation/run")
def run_evaluation(rid: str, body: dict = Body(...), h: dict = Depends(_session)):
    r = _rfq(rid, h)
    try:
        criteria = quotes.validate_criteria(body.get("criteria"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    reqs = [q for q in store.list_requests(rfq_id=r["id"]) if q["status"] == "quoted"]
    if not reqs:
        raise HTTPException(400, "No quotes received yet")
    by_quote = {q["id"]: q["quotation"] for q in reqs}
    rows = {qid: {} for qid in by_quote}
    for c in criteria:  # numeric / threshold: calculated by rule, same result every run
        if c["kind"] != "descriptive":
            for qid, x in quotes.score_rules(by_quote, c).items():
                rows[qid][c["id"]] = x
    ai = quote_ai.score_descriptive(r, reqs, criteria)  # descriptive: AI with a reason
    for qid, a in ai.items():
        rows[qid].update(a["scores"])
    names = {q["id"]: q["seller_name"] for q in reqs}
    r["evaluation"] = {
        "criteria": criteria, "run_at": store.now(),
        "results": [{"request_id": qid, "seller_name": names[qid], "rank": i, "total": tot,
                     "scores": rows[qid], "risks": ai.get(qid, {}).get("risks", []),
                     "points_to_confirm": ai.get(qid, {}).get("points_to_confirm", []),
                     "landed_total": by_quote[qid]["totals"]["landed_total"]}
                    for i, (qid, tot) in enumerate(quotes.weighted(rows, criteria), 1)]}
    store.save_rfq(r)
    return r["evaluation"]


@app.get("/api/rfqs/{rid}/evaluation")
def get_evaluation(rid: str, h: dict = Depends(_session)):
    return _rfq(rid, h).get("evaluation")


@app.post("/api/rfqs/{rid}/quotes/{qid}/accept")
def accept_quote(rid: str, qid: str, h: dict = Depends(_session)):
    r = _rfq(rid, h)
    reqs = store.list_requests(rfq_id=r["id"])
    target = next((q for q in reqs if q["id"] == qid), None)
    if not target or target["status"] != "quoted":
        raise HTTPException(404, "Quote not found")
    if any(q.get("outcome") == "accepted" for q in reqs):
        raise HTTPException(409, "A quote has already been accepted for this RFQ")
    for q in reqs:
        if q["status"] == "quoted":
            q["outcome"] = "accepted" if q["id"] == qid else "not_selected"
            store.save_request(q)
    r["accepted_request"] = qid
    store.save_rfq(r)
    return {"requests": [_buyer_request_view(q) for q in store.list_requests(rfq_id=r["id"])]}


# ── Quote requests: supplier side ────────────────────────────────────────────
def _seller_req(qid: str, h: dict) -> tuple[dict, dict]:
    u = _user("seller", h)
    q = store.load_request(qid)
    if not q or q["seller_id"] != u["id"]:  # a supplier never sees another supplier's request
        raise HTTPException(404, "Quote request not found")
    return u, q


def _seller_view(q: dict, full: bool = True) -> dict:
    out = {k: q.get(k) for k in ("id", "buyer_name", "deadline", "sent_at", "viewed_at", "submitted_at",
                                 "decline_reason", "revision", "outcome")}
    out["status"] = quotes.effective_status(q)
    out["rfq"] = q["rfq"] if full else {k: q["rfq"][k] for k in ("ref", "title")}
    out["open"] = out["status"] in ("sent", "viewed", "quoted") and not q.get("outcome")
    if full:
        out.update({k: q.get(k) for k in ("fit", "quotation", "draft", "questions", "checks")})
    return out


def _editable(q: dict) -> None:
    if q.get("outcome"):
        raise HTTPException(409, "The buyer has already decided on this RFQ")
    if q["status"] == "declined":
        raise HTTPException(409, "You declined this request")
    if quotes.deadline_passed(q["deadline"]):
        raise HTTPException(409, "The quote deadline has passed")


@app.get("/api/seller/me")
def seller_me(h: dict = Depends(_session)):
    s = store.seller(_user("seller", h)["id"])
    return {k: s[k] for k in ("id", "name", "city", "category_label", "profile")}


@app.get("/api/seller/requests")
def seller_requests(h: dict = Depends(_session)):
    u = _user("seller", h)
    return [_seller_view(q, full=False) for q in store.list_requests(seller_id=u["id"])]


@app.get("/api/seller/requests/{qid}")
def seller_request(qid: str, h: dict = Depends(_session)):
    _, q = _seller_req(qid, h)
    if q["status"] == "sent" and not quotes.deadline_passed(q["deadline"]):
        q["status"], q["viewed_at"] = "viewed", store.now()
        store.save_request(q)
    return _seller_view(q)


@app.get("/api/seller/requests/{qid}/rfq.docx")
def seller_rfq_docx(qid: str, role: str | None = None, uid: str | None = None, h: dict = Depends(_session)):
    _, q = _seller_req(qid, {**h, "role": h["role"] or role, "id": h["id"] or uid})
    p = store.request_path(q["id"], "docx")
    if not p.exists():
        raise HTTPException(404, "No RFQ document for this request")
    return FileResponse(p, filename=f"{q['rfq']['ref']}.docx",
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@app.post("/api/seller/requests/{qid}/decline")
def seller_decline(qid: str, body: dict = Body(...), h: dict = Depends(_session)):
    _, q = _seller_req(qid, h)
    _editable(q)
    if q["status"] == "quoted":
        raise HTTPException(409, "You have already submitted a quotation")
    reason = str(body.get("reason") or "").strip()
    if not reason:
        raise HTTPException(400, "Give a reason for declining")
    q["status"], q["decline_reason"], q["declined_at"] = "declined", reason[:500], store.now()
    return _seller_view(store.save_request(q))


@app.post("/api/seller/requests/{qid}/draft")
def seller_draft(qid: str, body: dict = Body(...), h: dict = Depends(_session)):
    u, q = _seller_req(qid, h)
    _editable(q)
    if body.get("mode") == "template":
        q["draft"], q["questions"] = quote_ai.template(q["rfq"], store.seller(u["id"])), []
    elif body.get("mode") == "ai":
        q["draft"], q["questions"] = quote_ai.draft(q["rfq"], store.seller(u["id"]))
    else:
        raise HTTPException(400, "Unknown mode")
    q["checks"] = quotes.pre_send_checks(q["draft"], q["rfq"], q["deadline"])
    return _seller_view(store.save_request(q))


@app.post("/api/seller/requests/{qid}/ai-answers")
def seller_ai_answers(qid: str, body: dict = Body(...), h: dict = Depends(_session)):
    _, q = _seller_req(qid, h)
    _editable(q)
    if not q.get("draft"):
        raise HTTPException(409, "Start an AI-assisted draft first")
    q["draft"] = quotes.clean_quotation(quote_ai.apply_answers(q["draft"], body.get("answers") or {}), q["rfq"])
    q["questions"] = []
    q["checks"] = quotes.pre_send_checks(q["draft"], q["rfq"], q["deadline"])
    return _seller_view(store.save_request(q))


@app.post("/api/seller/requests/{qid}/upload")
async def seller_upload(qid: str, file: UploadFile = File(...), h: dict = Depends(_session)):
    _, q = _seller_req(qid, h)
    _editable(q)
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "File too large (20 MB max)")
    try:
        blocks = ingest.to_blocks(data, file.filename or "quotation")
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not blocks:
        raise HTTPException(400, "No text found in the document")
    q["draft"] = {**quote_ai.extract(blocks, q["rfq"]), "filename": file.filename}
    q["questions"] = []
    q["checks"] = quotes.pre_send_checks(q["draft"], q["rfq"], q["deadline"])
    return _seller_view(store.save_request(q))


@app.put("/api/seller/requests/{qid}/quotation")
def seller_save(qid: str, body: dict = Body(...), h: dict = Depends(_session)):
    """Save the draft being edited (any mode); totals and checks are recomputed by rule."""
    _, q = _seller_req(qid, h)
    _editable(q)
    d = quotes.clean_quotation(body.get("quotation") or {}, q["rfq"])
    q["draft"] = {**d, "filename": (q.get("draft") or {}).get("filename")}
    q["checks"] = quotes.pre_send_checks(d, q["rfq"], q["deadline"])
    return _seller_view(store.save_request(q))


@app.post("/api/seller/requests/{qid}/submit")
def seller_submit(qid: str, h: dict = Depends(_session)):
    """Send (or revise, until the deadline) the quotation; blocked while a pre-send check fails."""
    _, q = _seller_req(qid, h)
    _editable(q)
    if not q.get("draft"):
        raise HTTPException(400, "Create the quotation first")
    d = {**quotes.clean_quotation(q["draft"], q["rfq"]), "filename": q["draft"].get("filename")}
    q["checks"] = quotes.pre_send_checks(d, q["rfq"], q["deadline"])
    if quotes.has_errors(q["checks"]):
        store.save_request(q)
        raise HTTPException(400, "Fix the flagged issues before sending: "
                            + "; ".join(c["message"] for c in q["checks"] if c["level"] == "error"))
    q["quotation"], q["status"] = d, "quoted"
    q["revision"] = (q.get("revision") or 0) + 1
    q["submitted_at"] = store.now()
    return _seller_view(store.save_request(q))


# ── SPA ──────────────────────────────────────────────────────────────────────
DIST = Path(os.getenv("WEB_DIST", Path(__file__).resolve().parents[2] / "web" / "dist"))
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        f = DIST / path
        if path and f.is_file() and DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
