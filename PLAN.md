# CapabilityX POC — Plan

## Context
A crude demo for clients and investors. A buyer either **uploads their own RFQ** or **builds one
with a chatbot**. Manufacturing suppliers are then gated, matched and scored, with a reason for
every result.

- The CSV MSMEs are **reference data**: they set the data shape and realistic values. They are not
  the subject of the demo.
- The seller pool is **planted demo data, manufacturers only**.
- The **VoltEdge RFQ sheet is the template format**: an RFQ detail header, sections 1–14 and
  buckets **A** (supplier response schedules A1–A11), **B** (quotation/cost breakdown B1–B4),
  **C** (compliance matrix + declarations), **D** (submission checklist). Generated RFQs must look
  like that.
- Keep the architecture simple and the deployment easy.

Folder: `C:\Users\tanuj\OneDrive\Desktop\QistonPe\CapabilityX_POC\`. Its older PLAN.md will be
replaced by this one.

## Stack (1 container)
```
CapabilityX_POC/
├── Dockerfile            # stage 1 npm build web/ ; stage 2 python:3.11-slim + uvicorn, serves web/dist
├── README.md             # local run + `gcloud run deploy capabilityx --source .`
├── api/
│   ├── main.py           # FastAPI routes + static SPA
│   ├── gemini.py         # genai.Client(vertexai=True, project=qistonpe-project-22810, location=global), JSON mode, retry
│   ├── ingest.py         # upload -> numbered blocks (python-docx paras+table rows / pymupdf pages / Gemini for scans)
│   ├── rfq_builder.py    # chatbot: slot-filling over a template; renders the RFQ .docx (python-docx)
│   ├── pipeline.py       # analyze_rfq -> shortlist -> match_seller
│   ├── scoring.py        # pure function: gate + score
│   ├── prompts.py
│   ├── tools/build_seed.py   # one-off: CSVs -> catalog.json + reference value ranges
│   ├── tools/gen_sellers.py  # one-off: Gemini plants ~25 manufacturer sellers -> sellers.json
│   └── data/  catalog.json · sellers.json · templates/*.json · users.json · rfqs/<id>.json
└── web/                  # React + Vite + Tailwind + react-router (as in opportunityX_frontend)
```
No database, RabbitMQ, NestJS, Redis or compose. Storage is JSON files. Gemini calls run
synchronously behind a spinner, with the Cloud Run timeout set to 300 s. The Vertex client and
retry pattern are copied in slimmed-down form from
`opportunityX_AI-Workers/app/services/gemini_client.py`.

## 1. RFQ templates (hardcoded, VoltEdge structure)
One **shared skeleton**, `templates/_skeleton.json`, holds the VoltEdge sections 1–14 and buckets
A–D as boilerplate text with `{{slots}}`. Each category template adds its own slots and option
lists.

| Template | Example category-specific slots (with choice chips) |
|---|---|
| Sheet-metal pressed/bent part (VoltEdge) | material grade (CRCA IS 513 / HR / SS304 / Al), thickness, route (laser/blanking, press, bend, machining), finish (zinc+passivation / powder coat / none) |
| CNC machined component | material, tolerances, critical features, heat treatment, finish |
| Fasteners | standard (IS/DIN/ISO), size range, grade/property class, coating |
| Castings / forgings | process, material grade, weight range, machining required, NDT |
| Fabricated structures | material, welding standard, size/weight, painting spec |
| Transformer / electrical equipment | rating kVA, voltage, cooling, standards (IS 2026/BIS), type tests |

Common slots for all templates (the VoltEdge buckets):
- **Header:** buyer, quantity, schedule, delivery model/frequency, payment days.
- **§6 quality:** ISO 9001 / IATF / ISO 14001 / 45001, each Mandatory / Preferred / Not needed.
- **§10 financial:** min current ratio, positive net worth, no default.
- **§11 ESG.**
- **§13 evaluation weights.**
- **A:** schedules auto-included per template.
- **B:** cost elements per template.
- **C:** compliance rows generated from the requirements.
- **D:** checklist.

**Every slot carries `data_point_ids` (catalog) plus a default `mandatory|scored`.** A generated
RFQ therefore arrives already mapped, with no extraction guesswork.

## 2. Chatbot RFQ builder (Flow B, the main demo moment)
1. The buyer types a need ("10k steel brackets for EV, JIT Pune").
2. Gemini **selects a template** (enum of template IDs) and pre-fills any slots it can from the text.
3. The bot asks the missing slots **bucket by bucket**, 3–5 questions per turn, with option chips
   from the template ("Surface finish? Zinc plating / Powder coat / None"). Gemini only chooses
   which slots to ask and parses the answers into slot values. The backend validates each value
   against the slot type and options.
4. A live preview of the RFQ appears on the side, with unanswered required slots flagged.
5. On Approve, the backend renders a **VoltEdge-style .docx** from skeleton + slots (downloadable)
   and creates the requirements list from the slots. The flow then continues at the Review step.
6. **Flow C** (pick a template and fill a form) reuses the same slots as a plain form, with no
   extra logic.

## 3. Upload any RFQ (Flow A)
1. Ingest the upload into numbered blocks.
2. One Gemini call returns `{summary, requirements:[{text, source_block_ids, data_point_ids (catalog enum), mandatory|scored}]}`.
   The backend checks the IDs and attaches the source quote. A requirement with no mapping is shown
   as "Not covered by supplier data" and left out of scoring.
3. → Review.

## 4. Review → match → score (shared by all flows)
1. **Review:** an editable requirements table (text, type, mapped point, add/delete). Confirm
   freezes the RFQ version.
2. **Shortlist:** one Gemini call sees the RFQ summary plus a one-line profile of every seller and
   returns up to ~10 relevant seller IDs with reasons. The others are listed as "Not relevant:
   <reason>".
3. **Match:** one Gemini call per shortlisted seller, in parallel, at temperature 0 with a fixed
   seed. It returns per requirement `{full|partial|not|na, reason}` from that seller's values. The
   result is cached in the RFQ JSON.
4. **Score (code):**
   - Any mandatory "not" → rejected, with the requirement that caused it.
   - Otherwise full = 1, partial = 0.5, not / na = 0. Category = mean. Total = equal-weight mean of
     the categories present (1/6 each).
   - If everyone is rejected → empty ranking plus the rejected list.
   - Re-scoring never calls the LLM again, so the same input always gives the same score.

## 5. Seller data (planted)
- `build_seed.py` takes the catalog (~85 points across the 6 categories) from the two CSVs, with
  hand fixes (Remi/Transcore row shift, ₹ encoding).
- `gen_sellers.py` uses Gemini to plant **~25 fictional manufacturing MSMEs** across the template
  categories (sheet metal, CNC, fasteners, castings/forgings, fabrication, transformers/electrical).
  - The real CSV rows serve as style examples.
  - Quality is deliberately mixed (strong, average, gaps, missing data), so the gates, partial
    matches and the Rejected view all appear.
  - Saved once as hardcoded `sellers.json` for you to review. Nothing is generated at demo time.

## Screens (basic Tailwind)
1. Pick a demo buyer → My RFQs (filtered by buyer, BRD criterion 5)
2. New RFQ: **Chat to build** | **Upload** | **From template**
3. Chat builder: chat on the left, live RFQ preview on the right, Approve + download .docx
4. Review requirements
5. Results: ranked + Rejected + Not relevant
6. Supplier detail: 6 category scores, per requirement status / value / reason

## Order of work
1. Skeleton + sheet-metal template from VoltEdge; catalog; `gen_sellers.py` → you review sellers
2. Pipeline (analyze, shortlist, match, score), run from the CLI on VoltEdge
3. Chat builder + .docx render (sheet-metal template first, then the other 5)
4. UI screens
5. Dockerfile + Cloud Run deploy

## Verification
- CLI: VoltEdge upload → requirements mapped; scoring twice gives the same result.
- Chat: "need 5000 M10 bolts zinc plated" → fasteners template chosen, the bot asks only missing
  slots, the rendered .docx has sections 1–14 + A–D, and the flow lands in Review with mapped
  requirements.
- Results show ranked, rejected (with the failing requirement) and not-relevant sellers.
- Buyer A cannot open buyer B's RFQ (404).
- `docker build && docker run` full flow locally, then the same on the Cloud Run URL.
