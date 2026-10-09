"""JSON-file storage. Static data (catalog, sellers, templates) is read once;
RFQs live one-per-file under RFQ_DIR, quote requests one-per-file under QUOTE_DIR."""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
RFQ_DIR = Path(os.getenv("RFQ_DIR", DATA / "rfqs"))
RFQ_DIR.mkdir(parents=True, exist_ok=True)
QUOTE_DIR = Path(os.getenv("QUOTE_DIR", DATA / "quotes"))
QUOTE_DIR.mkdir(parents=True, exist_ok=True)
_lock = threading.Lock()


def _load(name: str):
    return json.loads((DATA / name).read_text("utf-8"))


@lru_cache
def catalog() -> dict:
    return _load("catalog.json")


@lru_cache
def catalog_index() -> dict[str, dict]:
    return {d["id"]: d for d in catalog()["data_points"]}


@lru_cache
def sellers() -> list[dict]:
    return _load("sellers.json")


def seller(sid: str) -> dict | None:
    return next((s for s in sellers() if s["id"] == sid), None)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex[:10]


def rfq_path(rid: str, ext: str = "json") -> Path:
    return RFQ_DIR / f"{rid}.{ext}"


def save_rfq(rfq: dict) -> dict:
    rfq["updated_at"] = now()
    with _lock:
        tmp = rfq_path(rfq["id"], "json.tmp")
        tmp.write_text(json.dumps(rfq, indent=1, ensure_ascii=False), "utf-8")
        tmp.replace(rfq_path(rfq["id"]))
    return rfq


def load_rfq(rid: str) -> dict | None:
    if not rid.isalnum():
        return None
    p = rfq_path(rid)
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def list_rfqs(buyer_id: str) -> list[dict]:
    out = []
    for p in RFQ_DIR.glob("*.json"):
        r = json.loads(p.read_text("utf-8"))
        if r.get("buyer_id") == buyer_id:
            out.append(r)
    return sorted(out, key=lambda r: r.get("created_at", ""), reverse=True)


# ── quote requests (one per RFQ x seller) ────────────────────────────────────
def request_path(qid: str, ext: str = "json") -> Path:
    return QUOTE_DIR / f"{qid}.{ext}"


def save_request(q: dict) -> dict:
    q["updated_at"] = now()
    with _lock:
        tmp = request_path(q["id"], "json.tmp")
        tmp.write_text(json.dumps(q, indent=1, ensure_ascii=False), "utf-8")
        tmp.replace(request_path(q["id"]))
    return q


def load_request(qid: str) -> dict | None:
    if not qid.isalnum():
        return None
    p = request_path(qid)
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def list_requests(rfq_id: str | None = None, seller_id: str | None = None) -> list[dict]:
    out = []
    for p in QUOTE_DIR.glob("*.json"):
        q = json.loads(p.read_text("utf-8"))
        if (rfq_id is None or q.get("rfq_id") == rfq_id) and (seller_id is None or q.get("seller_id") == seller_id):
            out.append(q)
    return sorted(out, key=lambda q: q.get("sent_at", ""), reverse=True)
