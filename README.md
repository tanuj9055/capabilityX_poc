# CapabilityX POC

A buyer uploads an RFQ, builds one by chatting, or fills a template. Manufacturing MSMEs are then
gated, matched and scored, with a reason for every result. See `PLAN.md` for the design.

One container: FastAPI (`api/app`) serves `/api/*` and the built React SPA (`web/dist`). Storage is
JSON files (`data/rfqs`, `data/quotes`). Sign-in is a demo role picker with no password: a **Buyer**
types a company name (its slug is the buyer id, so the same name sees the same RFQs) and a **Seller**
picks one of the 4 MSMEs. The session lives in sessionStorage, so a buyer tab and a seller tab can be
open side by side. RFQs created before sign-in existed (random-id buyers) are orphaned. Gemini runs on Vertex AI (project `qistonpe-project-22810`, location `global`).

## Run locally

```bash
# backend (needs Vertex credentials, see api/.env)
cd api
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8080 --reload

# frontend (dev server with hot reload, proxies /api -> :8080)
cd web
npm install
npm run dev          # http://localhost:5174
# or: npm run build  -> the backend then serves the SPA at http://localhost:8080
```

`api/.env`:
```
GOOGLE_APPLICATION_CREDENTIALS=C:/.../gcp-credentials.json
GCP_PROJECT=qistonpe-project-22810
GEMINI_MODEL=gemini-3.5-flash
```

## Docker

```bash
docker build -t capabilityx .
docker run -p 8080:8080 \
  -e GOOGLE_APPLICATION_CREDENTIALS=/creds/key.json -v /path/to/key.json:/creds/key.json:ro \
  capabilityx
```

## Deploy to Cloud Run

```bash
gcloud run deploy capabilityx --source . --region asia-south1 \
  --project qistonpe-project-22810 --allow-unauthenticated \
  --timeout 300 --memory 1Gi --max-instances 1 \
  --set-env-vars GCP_PROJECT=qistonpe-project-22810,GEMINI_MODEL=gemini-3.5-flash
```
The runtime service account needs the **Vertex AI User** role. With `--max-instances 1` all demo
users share one instance, so RFQs persist until it restarts. The filesystem is ephemeral, which is
fine for a demo.

## Demo script

1. Open the app (no sign-in), click **New RFQ**, then **Upload** an RFQ. Requirements are extracted and mapped
   (Review). Click **Confirm**: relevant MSMEs pass the mandatory gate or are rejected with the reason,
   and the rest are ranked. The pool is the 4 real MSMEs (2 transformer makers, a fastener maker, a
   fabrication / machining shop), so transformer, fastener or fabrication RFQs give the fullest results.
2. **New RFQ**, then **Chat**: "Need 5000 M10 hex bolts, zinc plated". The assistant picks the
   fasteners template and asks only what's missing, while the preview fills live. **Approve**
   produces the .docx (VoltEdge format, sections 1–14 + A–D, ~13 pages), and the flow continues to
   Review and Results.
3. **From template**: the same slots as a plain form.
4. **Quotes** (transformer RFQ → Remi and Transcore pass the gate). Buyer: on **Results**, tick the
   suppliers, pick a deadline and click **Request quotes**. In a second tab, sign in as the seller and open
   **Quote Requests**: read the understanding and your fit, then quote by **Template**, **AI-assisted draft**
   (the AI fills lines and proof, then asks only what you know: prices, lead time, validity…) or **Upload**,
   or **Decline** with a reason. Pre-send checks block sending on a missing price, a mandatory deviation,
   validity shorter than asked, or a stated total that doesn't match. Back as the buyer, open **Quote
   Evaluation**: tracker, quotes side by side, weighted criteria (must total 100%), **Run analysis** and
   **Accept**. Numeric and threshold criteria are calculated by rule, so they give the same result every run.
   Descriptive criteria are scored by AI with a reason. The saved analysis reopens unchanged.

## Data / one-off tools (`api/tools`)

| Script | Output |
|---|---|
| `build_seed.py` | `catalog.json` (88 data points, 6 categories) + `sellers.json`: the seller pool = the 4 real MSMEs in the 2 CSVs (Remi, Gurunanak, KCS, Transcore) |
| `build_templates.py` | `templates/_skeleton.json` (VoltEdge structure) + 6 category templates + `base.docx` |
| `quote_e2e.py` | end-to-end API check of the quote module, buyer and sellers, real Gemini (`--keep` writes to the real data dirs) |
| `cli.py` | `cli.py upload <rfq.docx>` / `cli.py chat "<need>"`: pipeline check without the UI |

Scoring (`app/scoring.py`) is a pure function. Any mandatory requirement that is "not met"
rejects the seller. Otherwise Met = 1, Partial = 0.5, Not met / No data = 0; each category is
the mean of its requirements, and the total is the equal-weight mean of the categories. Matches
are cached in the RFQ, so re-scoring never calls the LLM.

Quotes (`app/quotes.py`, pure): line totals, GST, freight and landed total are calculated by rule.
Pre-send checks and numeric/threshold scoring are also pure. Numeric scores 100·best/value (or
value/best when higher is better). Threshold gives 100 within the limit and falls linearly to 0 at 2× the
limit. The weighted total is Σ weight·score/100. The LLM parts are in `app/quote_ai.py`.
