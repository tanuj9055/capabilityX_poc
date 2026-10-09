"""CLI check of the pipeline without the web app.

    python tools/cli.py upload <file.docx|pdf>      # analyze -> gate -> score (x2, compare)
    python tools/cli.py chat "need 5000 M10 bolts zinc plated"   # template select + first turn
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from app import ingest, pipeline, rfq_builder, store  # noqa: E402


def upload(path: str) -> None:
    p = Path(path)
    blocks = ingest.to_blocks(p.read_bytes(), p.name)
    print(f"{len(blocks)} blocks")
    a = pipeline.analyze_rfq(blocks)
    print(f"\n{a['title']} — {a['summary']}\n")
    for r in a["requirements"]:
        print(f"  {r['id']:4s} {r['type']:9s} {r['text'][:80]:80s} {r['data_point_ids'] or 'NOT COVERED'}")
    rfq = {"id": "cli", "title": a["title"], "summary": a["summary"], "requirements": a["requirements"]}
    pipeline.run_matching(rfq)
    res1 = pipeline.results(rfq)
    res2 = pipeline.results(json.loads(json.dumps(rfq)))
    print("\nscoring deterministic:", res1 == res2)
    print("\nRANKED")
    for x in res1["ranked"]:
        print(f"  #{x['rank']} {x['total']:5.1f} {x['name']} ({x['city']})  "
              + " ".join(f"{k}:{v['score']:.0f}" for k, v in x["categories"].items()))
    print("REJECTED")
    for x in res1["rejected"]:
        print(f"  {x['name']}: " + "; ".join(f["text"][:60] + " — " + f["reason"][:80] for f in x["failed"]))
    for x in res1["errors"]:
        print(f"  ERROR {x['name']}: {x['reason']}")
    out = ROOT / "app" / "data" / "rfqs" / "_cli_last.json.txt"
    out.write_text(json.dumps(rfq, indent=1, ensure_ascii=False), "utf-8")


def chat(msg: str) -> None:
    tid, reason = rfq_builder.select_template(msg)
    print("template:", tid, "—", reason)
    r = {"id": "clichat", "template_id": tid, "slots": {"buyer": "Demo Buyer"}, "messages": [],
         "created_at": store.now()}
    rfq_builder.chat_turn(r, msg, None)
    print("slots:", r["slots"])
    print("bot:", r["messages"][-1]["text"])
    for q in r["messages"][-1]["questions"]:
        print("  ?", q["question"], q.get("options", ""))


if __name__ == "__main__":
    {"upload": upload, "chat": chat}[sys.argv[1]](sys.argv[2])
