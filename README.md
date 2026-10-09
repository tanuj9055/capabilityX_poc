# CapabilityX POC

A buyer uploads an RFQ, builds one by chatting, or fills a template. Manufacturing MSMEs are then
gated, matched and scored, with a reason for every result. See `PLAN.md` for the design.

One container: FastAPI (`api/app`) serves `/api/*` and the built React SPA (`web/dist`). Storage is
JSON files (`data/rfqs`, `data/quotes`). Sign-in is a demo role picker with no password: a **Buyer**
types a company name (its slug is the buyer id, so the same name sees the same RFQs) and a **Seller**
picks one of the 4 MSMEs. The session lives in sessionStorage, so a buyer tab and a seller tab can be
open side by side. RFQs created before sign-in existed (random-id buyers) are orphaned. Gemini runs on Vertex AI (project `qistonpe-project-22810`, location `global`).

## Getting started (run it on your machine)

### 1. Prerequisites

| Tool | Version | Check |
|---|---|---|
| Git | any | `git --version` |
| Python | 3.11 or newer | `python --version` |
| Node.js | 20 or newer (npm comes with it) | `node --version` |
| Docker (optional) | any | only if you want the one-container route in step 6 |

You also need the **GCP service-account key file** (`gcp-credentials.json`). The app calls Gemini on
Vertex AI in project `qistonpe-project-22810`, and the key is what lets it do that. It is **not in this
repo**: ask the project owner to send it to you privately. Without it the app still opens, but every
step that uses AI (reading an RFQ, chat, matching, quote analysis) fails with a 500 error.

### 2. Clone

```bash
git clone https://github.com/tanuj9055/capabilityX_poc.git
cd capabilityX_poc
```

### 3. Configure the backend (`api/.env`)

Put the key file in the `api/` folder as `api/gcp-credentials.json` (the `.gitignore` keeps it out of
git), then create the env file from the example:

```bash
cp api/.env.example api/.env        # Windows PowerShell: Copy-Item api/.env.example api/.env
```

`api/.env` then contains:

```
GOOGLE_APPLICATION_CREDENTIALS=gcp-credentials.json
GCP_PROJECT=qistonpe-project-22810
GCP_LOCATION=global
GEMINI_MODEL=gemini-3.5-flash
```

| Variable | Meaning |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to the key file. Relative paths are resolved from `api/`, which is where you start the backend. An absolute path also works (on Windows use forward slashes, e.g. `C:/keys/gcp-credentials.json`). |
| `GCP_PROJECT` | GCP project that Vertex AI is billed to. |
| `GCP_LOCATION` | Vertex AI location. Keep `global`. |
| `GEMINI_MODEL` | Gemini model name. |

Nothing else is needed: there is no database. RFQs and quotes are saved as JSON files in
`api/app/data/rfqs` and `api/app/data/quotes`. The 4 MSMEs and the catalog are already in the repo.

### 4. Start the backend (terminal 1)

```bash
cd api
python -m venv .venv
# activate it:
#   macOS / Linux:        source .venv/bin/activate
#   Windows PowerShell:   .venv\Scripts\Activate.ps1
#   Windows Git Bash:     source .venv/Scripts/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8080 --reload
```

Check it: <http://localhost:8080/docs> shows the API page.
Next time you only need to `cd api`, activate the venv and run the `uvicorn` line.

### 5. Start the frontend (terminal 2)

```bash
cd web
npm install
npm run dev
```

Open **<http://localhost:5174>**. The dev server forwards `/api` calls to the backend on port 8080,
so keep both terminals running. Then follow the **Demo script** below.

Single-server option: run `npm run build` in `web/` once instead of `npm run dev`. The backend then
serves the whole app at <http://localhost:8080> (re-run the build after frontend changes).

### 6. Or run everything in Docker (no Python or Node needed)

From the repo root, with the key file at `api/gcp-credentials.json`:

```bash
docker build -t capabilityx .

# macOS / Linux
docker run --rm -p 8080:8080 -e GOOGLE_APPLICATION_CREDENTIALS=/creds/key.json -v "$(pwd)/api/gcp-credentials.json:/creds/key.json:ro" capabilityx

# Windows Git Bash: same command with MSYS_NO_PATHCONV=1 in front, otherwise Git Bash rewrites
# /creds/key.json into a Windows path and every AI call fails
MSYS_NO_PATHCONV=1 docker run --rm -p 8080:8080 -e GOOGLE_APPLICATION_CREDENTIALS=/creds/key.json -v "$(pwd -W)/api/gcp-credentials.json:/creds/key.json:ro" capabilityx
```

Open <http://localhost:8080>. Data saved inside the container is lost when it stops.

### Troubleshooting

| Symptom | Fix |
|---|---|
| AI steps fail with 500, backend log mentions credentials / `DefaultCredentialsError` | `api/.env` is missing, or `GOOGLE_APPLICATION_CREDENTIALS` points to a file that doesn't exist. Start the backend from inside `api/`. |
| `403 Permission denied` from Vertex AI | The key's service account lacks the **Vertex AI User** role on `qistonpe-project-22810`. Ask the project owner. |
| Frontend loads but every action errors | The backend isn't running on port 8080. |
| `Address already in use` / port busy | Something else uses 8080 or 5174. Stop it, or start uvicorn with another `--port` and change the proxy target in `web/vite.config.js` to match. |
| PowerShell won't activate the venv | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. |

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
