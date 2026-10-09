"""RFQ templates: slot validation, preview/.docx rendering, requirements, chat turns."""
from __future__ import annotations

import copy
import json
import re
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import RGBColor

from . import gemini, prompts, store

TPL_DIR = store.DATA / "templates"
SKIP_VALUES = {"", "not needed", "no", "none", "not evaluated", "not specified", "not required"}
MAX_QUESTIONS = 4


# ── templates ────────────────────────────────────────────────────────────────
@lru_cache
def skeleton() -> dict:
    return json.loads((TPL_DIR / "_skeleton.json").read_text("utf-8"))


@lru_cache
def templates() -> dict[str, dict]:
    out = {}
    for p in sorted(TPL_DIR.glob("*.json")):
        if p.name.startswith("_"):
            continue
        t = json.loads(p.read_text("utf-8"))
        # merged slot list: header slots, category (technical) slots, then the rest of the common slots
        common = [dict(s) for s in skeleton()["common_slots"]]
        for s in common:
            if s["id"] in t.get("defaults", {}):
                s["default"] = t["defaults"][s["id"]]
        head = [s for s in common if s["bucket"] == "header"]
        rest = [s for s in common if s["bucket"] != "header"]
        t["all_slots"] = head + t["slots"] + rest
        t["slot_index"] = {s["id"]: s for s in t["all_slots"]}
        t["buckets"] = skeleton()["buckets"]
        out[t["id"]] = t
    return out


def template(tid: str) -> dict:
    return templates()[tid]


def template_public(t: dict) -> dict:
    return {k: t[k] for k in ("id", "name", "description", "all_slots", "buckets")}


# ── slot values ──────────────────────────────────────────────────────────────
def _match_option(v: str, options: list[str]) -> str | None:
    v = str(v).strip().lower()
    for o in options:
        if o.lower() == v:
            return o
    for o in options:
        if v and (v in o.lower() or o.lower() in v):
            return o
    return None


def validate(slot: dict, value):
    """Return the cleaned value, or None if invalid / empty."""
    if value is None:
        return None
    t = slot["type"]
    if t == "number":
        m = re.search(r"-?\d[\d,]*\.?\d*", str(value))
        if not m:
            return None
        n = float(m.group().replace(",", ""))
        return int(n) if n.is_integer() else n
    if t in ("choice", "level"):
        return _match_option(value, slot["options"])
    if t == "multi":
        items = value if isinstance(value, list) else re.split(r",|;|\band\b", str(value))
        picked = [o for o in (_match_option(i, slot["options"]) for i in items if str(i).strip()) if o]
        return list(dict.fromkeys(picked)) or None
    v = str(value).strip()
    return v or None


def apply_values(rfq: dict, values: dict) -> list[str]:
    """Validate + store values; return slot ids that were updated."""
    t = template(rfq["template_id"])
    done = []
    for sid, v in (values or {}).items():
        s = t["slot_index"].get(sid)
        if not s:
            continue
        cv = validate(s, v)
        if cv is not None:
            rfq["slots"][sid] = cv
            done.append(sid)
    return done


def effective(rfq: dict) -> dict:
    """Slot values with defaults + derived values applied."""
    t = template(rfq["template_id"])
    vals = {s["id"]: s["default"] for s in t["all_slots"] if "default" in s}
    vals.update({k: v for k, v in rfq["slots"].items() if v not in (None, "", [])})
    issue = date.fromisoformat(rfq["created_at"][:10])
    vals.setdefault("issue_date", f"{issue.day} {issue:%B %Y}")
    vals.setdefault("rfq_title", t["name"])
    due = issue + timedelta(days=14)
    vals.setdefault("quote_due", f"{due.day} {due:%B %Y}")
    return vals


def display(slot: dict | None, v) -> str:
    if isinstance(v, list):
        return ", ".join(map(str, v))
    if isinstance(v, (int, float)) and slot and slot.get("type") == "number" and v >= 1000:
        return f"{v:,}"
    return str(v)


# Non-data-point fields the chat still asks: who is issuing the RFQ (the document needs it and
# there is no sign-in to take it from). "buyer" is required; "contact" is optional.
ALWAYS_ASK = {"buyer", "contact"}


def is_required(s: dict) -> bool:
    """Required = a core field that maps to supplier data points (the ones that drive matching),
    plus the issuing company. Other document-only fields (title, delivery location, ...) are optional."""
    return bool(s.get("ask") and (s.get("data_point_ids") or s["id"] in ALWAYS_ASK))


def missing_required(rfq: dict) -> list[dict]:
    t = template(rfq["template_id"])
    vals = effective(rfq)
    return [s for s in t["all_slots"] if is_required(s) and vals.get(s["id"]) in (None, "", [])]


# ── rendering (shared by live preview + .docx) ───────────────────────────────
def _fmt(text: str, rfq: dict, t: dict, vals: dict) -> str:
    def rep(m):
        k = m.group(1)
        if k == "rfq_ref":
            return rfq.get("ref") or f"RFQ-{rfq['id'][:6].upper()}"
        if k in ("supplier_type", "purpose"):
            return t[k]
        s = t["slot_index"].get(k)
        v = vals.get(k)
        if v in (None, "", []):
            # required (data-point) fields are flagged; optional document fields read naturally
            return f"[{s['label'] if s else k}?]" if (not s or is_required(s)) else "to be confirmed"
        return display(s, v)
    return re.sub(r"\{\{(\w+)\}\}", rep, text)


def render_blocks(rfq: dict) -> list[dict]:
    """The RFQ document: VoltEdge structure, sections 1-14 + annexures A-D."""
    t = template(rfq["template_id"])
    vals = effective(rfq)
    out: list[dict] = []

    def emit(b):
        b = copy.deepcopy(b)
        if b.get("if") and str(vals.get(b["if"], "")).lower() in SKIP_VALUES:
            return
        if b["t"] == "include":
            for x in t["blocks"].get(b["key"], []):
                emit(x)
            return
        if b["t"] == "supply_table":
            q, n = vals.get("quantity"), vals.get("schedule_months")
            rows = [["Period", "Indicative quantity", "Planning basis"]]
            if isinstance(q, (int, float)) and isinstance(n, (int, float)) and 0 < n <= 24:
                n = int(n)
                per = [int(q) // n + (1 if i < int(q) % n else 0) for i in range(n)]
                rows += [[f"Month {i + 1}", f"{p:,} units", "Subject to approval and release schedule"]
                         for i, p in enumerate(per)]
                rows.append(["Total", f"{int(q):,} units", "Initial sourcing requirement"])
            else:
                rows.append(["[Supply period?]", "[Contract quantity?]", ""])
            b = {"t": "table", "header": True, "rows": rows}
        elif b["t"] == "cert_table":
            rows = [["Requirement", "Status"]]
            for s in t["all_slots"]:
                if s["type"] == "level":
                    rows.append([s["label"], display(s, vals.get(s["id"], "[?]"))])
            b = {"t": "table", "header": True, "rows": rows}
        elif b["t"] == "weights_table":
            b = {"t": "table", "header": True,
                 "rows": [["Evaluation category", "Indicative weight"]] + [[c, f"{w} percent"] for c, w in t["weights"]]}
        elif b["t"] == "compliance_table":
            reqs = requirements_from_slots(rfq)
            b = {"t": "table", "header": True,
                 "rows": [["Requirement", "Type", "Comply", "Partial", "Deviate", "Explanation or reference"]]
                 + [[r["text"], r["type"].title(), "", "", "", ""] for r in reqs]}
        if "text" in b:
            b["text"] = _fmt(b["text"], rfq, t, vals)
        if "rows" in b:
            b["rows"] = [[_fmt(c, rfq, t, vals) for c in row] for row in b["rows"]]
        out.append(b)

    for b in skeleton()["blocks"]:
        emit(b)
    return out


def render_docx(rfq: dict) -> Path:
    d = docx.Document(str(TPL_DIR / "base.docx"))
    body = d.element.body
    for el in list(body):
        if el.tag != qn("w:sectPr"):
            body.remove(el)
    vals = effective(rfq)
    ref = rfq.get("ref") or f"RFQ-{rfq['id'][:6].upper()}"
    _replace_runs(d.sections[0].header.paragraphs, str(vals.get("buyer", "")).upper())
    _replace_runs(d.sections[0].footer.paragraphs, f"{ref}   |   Page ", only_first_text=True)

    for b in render_blocks(rfq):
        k = b["t"]
        if k == "table":
            _add_table(d, b["rows"], b.get("header"))
        else:
            style = {"title": "Title", "sub": "Subtitle", "h1": "Heading 1", "h2": "Heading 2",
                     "bullet": "List Bullet", "num": "List Number"}.get(k, "Body Text")
            d.add_paragraph(b["text"], style=style)
    path = store.rfq_path(rfq["id"], "docx")
    d.save(str(path))
    return path


def _replace_runs(paragraphs, text: str, only_first_text: bool = False) -> None:
    for p in paragraphs:
        runs = [r for r in p.runs if r.text]
        if not runs:
            continue
        runs[0].text = text
        if not only_first_text:
            for r in runs[1:]:
                r.text = ""
        else:  # footer: keep PAGE / NUMPAGES fields, drop the old static "of" text once
            for r in runs[1:]:
                if "of" in r.text:
                    r.text = " of "
        return


def _add_table(d, rows: list[list[str]], header: bool) -> None:
    ncols = max(len(r) for r in rows)
    tb = d.add_table(rows=len(rows), cols=ncols)
    tb.style = d.styles["Table Grid"]
    tb.autofit = False
    widths = _col_widths(d, rows, ncols)
    for i, row in enumerate(rows):
        for j in range(ncols):
            cell = tb.cell(i, j)
            cell.width = widths[j]
            cell.text = row[j] if j < len(row) else ""
            if header and i == 0:
                shd = OxmlElement("w:shd")
                shd.set(qn("w:val"), "clear")
                shd.set(qn("w:fill"), "17365D")
                cell._tc.get_or_add_tcPr().append(shd)
                for r in cell.paragraphs[0].runs:
                    r.bold = True
                    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    d.add_paragraph("")


def _col_widths(d, rows: list[list[str]], ncols: int) -> list[int]:
    """Split the usable page width by each column's longest line (header included),
    so short columns (#, Type) stay narrow and long-text columns get the room."""
    sec = d.sections[0]
    usable = sec.page_width - sec.left_margin - sec.right_margin
    need = []
    for j in range(ncols):
        cells = [r[j] for r in rows if j < len(r)]
        longest = max(len(c) for c in cells)
        word = max((len(w) for c in cells for w in c.split()), default=0)  # never break a word
        need.append(min(max(longest, word + 7, 6), 60))  # +7 ~ cell padding
    total = sum(need)
    return [int(usable * n / total) for n in need]


# ── requirements from slots ──────────────────────────────────────────────────
def requirements_from_slots(rfq: dict) -> list[dict]:
    t = template(rfq["template_id"])
    vals = effective(rfq)
    disp = {k: display(t["slot_index"].get(k), v) for k, v in vals.items()}
    reqs = []
    for s in t["all_slots"]:
        if not s.get("data_point_ids"):
            continue
        v = vals.get(s["id"])
        if v in (None, "", []) or str(v).strip().lower() in SKIP_VALUES:
            continue
        kind = s["kind"]
        if s["type"] == "level":
            kind = "mandatory" if v == "Mandatory" else "scored"
        text = s["req"]
        for k, dv in disp.items():
            text = text.replace("{" + k + "}", dv)
        text = text.replace("{v}", display(s, v))
        text = re.sub(r"\{\w+\}", "the specified", text)
        reqs.append({"id": f"r{len(reqs) + 1}", "text": text, "type": kind,
                     "data_point_ids": list(s["data_point_ids"]), "source": f"slot:{s['id']}"})
    return reqs


# ── chat ─────────────────────────────────────────────────────────────────────
def select_template(message: str) -> tuple[str, str]:
    lines = "\n".join(f"- {t['id']}: {t['name']} — {t['description']} (keywords: {', '.join(t['keywords'])})"
                      for t in templates().values())
    r = gemini.generate_json(prompts.SELECT_TEMPLATE.format(templates=lines, message=message),
                             temperature=0, tag="select-template",
                             schema={"type": "OBJECT", "properties": {
                                 "template_id": {"type": "STRING", "enum": list(templates())},
                                 "reason": {"type": "STRING"}}, "required": ["template_id"]})
    tid = r.get("template_id")
    if tid not in templates():
        tid = "sheet_metal"
    return tid, r.get("reason", "")


# Slots the chat never asks: filled from the signed-in buyer / derived automatically.
NOT_ASKED = {"issue_date"}


def _question(s: dict, vals: dict) -> dict:
    q = {k: s[k] for k in ("id", "label", "type", "question", "options", "unit", "hint", "bucket") if k in s}
    if vals.get(s["id"]) not in (None, "", []):
        q["value"] = vals[s["id"]]  # pre-selected suggestion / current answer
    return q


def _askable(t: dict) -> list[dict]:
    """The chat only asks fields that map to supplier data points; other fields are still captured
    from free text and editable in the form, but never asked."""
    return [s for s in t["all_slots"]
            if (s.get("data_point_ids") or s["id"] in ALWAYS_ASK) and s["id"] not in NOT_ASKED]


def _next_questions(rfq: dict, focus: str | None = None) -> list[str]:
    """Bucket-by-bucket walk through every askable slot (defaults shown as suggestions).
    Required-but-empty slots come first; a requested focus bucket jumps the queue."""
    t = template(rfq["template_id"])
    asked = set(rfq.get("asked_all") or [])
    confirmed = set(rfq.get("confirmed") or [])
    if focus and any(s["bucket"] == focus for s in _askable(t)):
        in_bucket = [s for s in _askable(t) if s["bucket"] == focus]
        fresh = [s["id"] for s in in_bucket if s["id"] not in asked]
        return (fresh or [s["id"] for s in in_bucket])[:MAX_QUESTIONS + 1]
    miss = [s["id"] for s in missing_required(rfq)]
    if miss:
        first = t["slot_index"][miss[0]]["bucket"]
        ids = [i for i in miss if t["slot_index"][i]["bucket"] == first]
        # ask the RFQ contact together with the issuing company
        ids += [i for i in ALWAYS_ASK if i not in ids and i not in asked and i not in confirmed
                and t["slot_index"][i]["bucket"] == first]
        return ids[:MAX_QUESTIONS]
    pending = [s for s in _askable(t) if s["id"] not in asked and s["id"] not in confirmed]
    if not pending:
        return []
    first = pending[0]["bucket"]
    return [s["id"] for s in pending if s["bucket"] == first][:MAX_QUESTIONS + 1]


def chat_turn(rfq: dict, message: str | None, values: dict | None) -> dict:
    """Apply chip values and/or parse a free-text message; append bot reply + next questions."""
    t = template(rfq["template_id"])
    confirmed = set(rfq.get("confirmed") or [])
    updated = apply_values(rfq, values or {})
    confirmed |= set(updated)
    reply, focus = "", None
    if message and message.strip():
        rfq["messages"].append({"role": "user", "text": message.strip()})
        vals = effective(rfq)
        slot_lines = "\n".join(
            f"{s['id']} | {s['label']} | {s['type']} | "
            f"{'/'.join(s.get('options', [])) or s.get('unit', '')} | "
            f"{json.dumps(vals.get(s['id']), ensure_ascii=False) if s['id'] in vals else 'EMPTY'} | {s['bucket']}"
            for s in t["all_slots"])
        buckets = ", ".join(f"{b['id']}: {b['label']}" for b in t["buckets"])
        r = gemini.generate_json(prompts.CHAT_TURN.format(
            template_name=t["name"], buckets=buckets, slots=slot_lines,
            asked=", ".join(rfq.get("asked") or []) or "(none)", message=message), temperature=0, tag="chat-turn")
        got = apply_values(rfq, r.get("updates") or {})
        updated += got
        confirmed |= set(got)
        reply = r.get("reply") or ""
        focus = r.get("focus_bucket") if r.get("focus_bucket") in {b["id"] for b in t["buckets"]} else None
    elif values:
        rfq["messages"].append({"role": "user", "text": "; ".join(
            f"{t['slot_index'][k]['label']}: {display(t['slot_index'][k], rfq['slots'][k])}"
            for k in updated) or "(kept the suggested answers)"})
    # questions shown last turn count as answered once the buyer moves on (suggestion accepted)
    if values is not None or message:
        confirmed |= set(rfq.get("asked") or []) - {s["id"] for s in missing_required(rfq)}
    rfq["confirmed"] = sorted(confirmed)

    nxt = _next_questions(rfq, focus)
    rfq["asked"] = nxt
    rfq["asked_all"] = sorted(set(rfq.get("asked_all") or []) | set(nxt))
    if nxt:
        label = next(b["label"] for b in t["buckets"] if b["id"] == t["slot_index"][nxt[0]]["bucket"])
        lead = f"Next: {label}. Suggested answers are pre-selected — change any, then send."
        reply = f"{reply} {lead}".strip() if reply else ("Got it. " if updated else "") + lead
    else:
        reply = (reply + " " if reply else "") + (
            "That covers every section. Review the preview on the right, edit anything, then approve the RFQ. "
            "You can also ask me to revisit any topic (e.g. \"ask about quality\").")
    vals = effective(rfq)
    rfq["messages"].append({"role": "bot", "text": reply.strip(),
                            "questions": [_question(t["slot_index"][i], vals) for i in nxt]})
    return rfq


def understanding_from_slots(rfq: dict) -> dict:
    """Same shape as the upload flow's AI-extracted understanding, built from the slots."""
    t = template(rfq["template_id"])
    vals = effective(rfq)

    def dv(k):
        v = vals.get(k)
        return display(t["slot_index"].get(k), v) if v not in (None, "", []) else None
    qty, months = dv("quantity"), dv("schedule_months")
    return {
        "item": dv("rfq_title"), "quantity": f"{qty} units" if qty else None,
        "contract_period": f"{months} months" if months else None,
        "delivery_location": dv("delivery_location"), "delivery_schedule": dv("delivery_model"),
        "payment_terms": f"{dv('payment_days')} days from GRN" if dv("payment_days") else None,
        "commercial_terms": f"INR, GST extra, freight {dv('freight')}" if dv("freight") else None,
        "key_dates": [{"label": "Issue date", "date": dv("issue_date")},
                      {"label": "Quotation due", "date": dv("quote_due")}],
        "technical_specs": [{"label": s["label"], "value": dv(s["id"])} for s in t["slots"] if dv(s["id"])][:8],
        "documents_required": ["Signed RFQ response", "Certificates (ISO / product)",
                               "Latest audited financials", "Equipment list"],
        "evaluation_basis": "Mandatory requirements are pass/fail; then weighted: "
                            + ", ".join(f"{c} {w}%" for c, w in t["weights"]),
    }
