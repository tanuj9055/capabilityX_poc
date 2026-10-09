"""All Gemini prompts in one place."""

SELECT_TEMPLATE = """A buyer is describing a manufacturing procurement need. Choose the RFQ template that fits best.

Templates:
{templates}

Buyer message:
\"\"\"{message}\"\"\"

Return JSON: {{"template_id": <one of the ids above>, "reason": <one short sentence>}}"""

CHAT_TURN = """You are an RFQ-building assistant for an Indian manufacturing buyer, filling a "{template_name}" RFQ.
You (1) parse the buyer's message into slot values and (2) notice when the buyer wants to discuss a topic.
Never invent values the buyer did not state or clearly imply.

Sections (bucket id: label): {buckets}

Slots (id | label | type | options/unit | current value | bucket):
{slots}

Questions the buyer was just asked: {asked}

Buyer message:
\"\"\"{message}\"\"\"

Rules:
- "updates": only slots the message gives a value for. For choice/level slots use one of the listed
  options verbatim. For multi slots return a list of options. For number slots return a plain number
  (convert "10k" -> 10000, "3 months" -> 3, "₹5 Cr" -> 500 when the unit is ₹ lakh).
  "use defaults / keep suggested / ok / fine" for the asked questions -> no updates needed.
- If the buyer changes an earlier answer, update that slot.
- "focus_bucket": the bucket id when the buyer asks to discuss / be asked about / change a topic (e.g.
  "ask about quality" -> "quality", "what about finances?" -> "financial", "payment terms" -> "delivery");
  otherwise null.
- "reply": one or two friendly sentences acknowledging what you captured (or that you will go through the
  requested topic). Do NOT list the questions — the UI shows them.

Return JSON: {{"updates": {{<slot_id>: value}}, "focus_bucket": str|null, "reply": str}}"""

ANALYZE_RFQ = """You are reading a buyer's RFQ / tender document (Indian manufacturing procurement). Extract the
supplier QUALIFICATION and EVALUATION requirements — things that can be checked against a supplier's
profile (capability, capacity, certifications, financials, organisation, policies, customer track record).
Skip pure response-format instructions, submission logistics and empty response tables.

The document is given as numbered blocks [n].

Map each requirement to 1-3 supplier data points from this catalog (id: label [category]). Use [] if no
catalog data point can verify it (e.g. unit price, drawing tolerances on a specific part).
{catalog}

"type": "mandatory" ONLY for explicit eligibility / pass-fail gates: a certification or approval the RFQ
calls mandatory/required, a stated minimum threshold (turnover, years, capacity), required process
capability or equipment, or a disqualifier (blacklisting, default, insolvency). Everything else —
preferred items, "assessment guides", general "supplier shall maintain / provide / disclose" contract
obligations, ESG/ethics expectations, documents to submit — is "scored". A typical RFQ has 3-8 mandatory
requirements.

Always include, as the first requirement and "mandatory", that the supplier already manufactures the kind
of item this RFQ buys (e.g. "Already manufactures sheet-metal pressed parts"), mapped to key_machinery,
nic_codes and hsn_products, with source_block_ids pointing at where the RFQ describes the item.

Keep requirements atomic and specific (quote thresholds: "Current ratio at least 1.2"). 12-30 requirements
for a typical RFQ; merge duplicates.

Document:
{blocks}

Return JSON:
{{"title": str, "buyer": str|null, "summary": "2-3 sentences: what is being bought, quantity, delivery, key terms",
  "item_category": str,
  "understanding": {{
    "item": str, "quantity": str|null, "contract_period": str|null,
    "delivery_location": str|null, "delivery_schedule": str|null,
    "payment_terms": str|null, "commercial_terms": str|null,
    "key_dates": [{{"label": str, "date": str}}],
    "technical_specs": [{{"label": str, "value": str}}],
    "documents_required": [str],
    "evaluation_basis": str|null}},
  "requirements": [{{"text": str, "type": "mandatory"|"scored", "data_point_ids": [str], "source_block_ids": [int]}}]}}

"understanding" is the structured tender summary a buyer would want at a glance: use null / [] for anything
the document does not state; keep values short (e.g. "10,000 units", "60 days from GRN"); at most 8
technical_specs, 8 key_dates and 8 documents_required; evaluation_basis = how suppliers are evaluated
(weights / L1 / QCBS) in one sentence."""

MAP_REQUIREMENTS = """Map each buyer requirement to the 1-3 supplier data points (from this catalog) that can verify it.
Use [] only when no data point can verify it (e.g. a unit price or a drawing tolerance).

Catalog (id: label [category]):
{catalog}

Requirements:
{requirements}

Return JSON: {{"mappings": [{{"n": <requirement number>, "data_point_ids": [str]}}]}}"""

MATCH = """You evaluate ONE supplier against an RFQ's requirements using ONLY the supplier data shown. Be strict
and literal; do not assume facts that are not in the data.

RFQ: {title}
Summary: {summary}

Supplier: {name} ({city}) — {profile}
Supplier data (data point id: value):
{values}

Requirements (id | type | text | relevant data points):
{requirements}

For each requirement return a status:
- "full": the data clearly shows the requirement is met.
- "partial": partly met, close to the threshold, outsourced where in-house was asked, or met with a caveat.
- "not": the data clearly shows it is NOT met (e.g. certificate absent, expired, lapsed, "under process" or
  "applied" — a certificate not yet granted is NOT met; threshold missed; negative net worth; blacklisted;
  default).
- "na": data not available — the relevant data is missing / null / "Not available", so it cannot be judged.
Reading the data:
- Values are self-reported survey text and may contain typos. If a value is ambiguous or looks like a
  typo of what is required (e.g. "Iso 1001" for ISO 9001), use "partial" and say what needs verifying —
  never "not" on an ambiguous value.
- The ISI mark is issued by BIS, so an ISI certificate counts as BIS certification.
- A certificate may be recorded under the sector-certification data point instead of its own one;
  read all relevant data points of a requirement together.
"reason": one short sentence citing the supplier's actual value.

Return JSON: {{"results": [{{"req_id": str, "status": "full"|"partial"|"not"|"na", "reason": str}}]}}"""

# ── quotations (supplier side) ───────────────────────────────────────────────
DRAFT_QUOTE = """You help an Indian manufacturing MSME draft a quotation in reply to a buyer's RFQ.
Use ONLY the RFQ and the supplier profile below. Never invent prices, lead times, validity, payment terms,
minimum order or material assumptions — those are the supplier's commercial decisions; ask for them instead.

RFQ {ref}: {title}
Summary: {summary}
Tender understanding: {understanding}
RFQ line items (desc | qty | unit):
{lines}
Mandatory requirements:
{mandatory}

Supplier: {name} ({city}) — {profile}
Supplier data (data point: value):
{values}

Return JSON:
{{"lines": [{{"desc": str, "qty": number, "unit": str}}],
  "supporting": {{"company": "one or two sentences of company details from the profile (legal structure, years, location, workforce)",
                 "certifications": [str], "past_orders": [str]}},
  "assumptions_hint": str,
  "questions": [{{"id": "unit_price_<line no>"|"lead_time_days"|"min_order"|"validity_days"|"payment_terms"|"payment_days"|"assumptions",
                 "question": str}}]}}
Rules:
- "lines": turn the RFQ line items and quantities into quotation lines (keep the RFQ quantities; split a line
  only if the RFQ clearly lists separate items).
- "certifications": only certificates present in the supplier data (with validity if shown).
- "past_orders": similar past supply / customers / largest order from the supplier data, as proof
  (e.g. "Supplies DISCOMs (MPPKVVCL)"). [] if none.
- "questions": ask only what you cannot know — one unit price question per line (id unit_price_1, unit_price_2 ...),
  then lead time in days, minimum order, quote validity in days, payment terms (credit days), material
  assumptions. Short, specific questions that mention the RFQ's own ask where it has one
  (e.g. "The RFQ asks for 60-day payment — what credit period do you offer?")."""

EXTRACT_QUOTE = """Read this supplier quotation (numbered text blocks) and convert it into a standard structure.
Copy values exactly as written; use null when the quotation does not state something. Do not compute
anything except converting "6 weeks" to 42 days, "3 months" to 90 days.

The RFQ it answers: {title}. RFQ line items: {lines}
Mandatory RFQ requirements (id: text):
{mandatory}

Quotation:
{blocks}

Return JSON:
{{"lines": [{{"desc": str, "qty": number|null, "unit": str, "unit_price": number|null}}],
  "gst_pct": number|null, "freight": number|null, "lead_time_days": number|null, "validity_days": number|null,
  "payment_terms": str|null, "payment_days": number|null, "min_order": number|null, "assumptions": str|null,
  "stated_total": number|null,
  "deviations": [{{"req_id": str, "note": str}}],
  "supporting": {{"company": str|null, "certifications": [str], "past_orders": [str]}}}}
"stated_total" = the grand total / total landed price the quotation itself states (incl. GST and freight), or null.
"deviations" = mandatory requirements the quotation explicitly says it does NOT comply with / takes exception to."""

SCORE_QUOTE = """You evaluate ONE supplier quotation for a buyer, on the buyer's descriptive criteria only, using ONLY
the quotation and supplier data shown. Be strict; do not assume facts that are not shown.

RFQ {ref}: {title}
Summary: {summary}

Supplier: {name} ({city}) — {profile}
Supplier data: {values}

Quotation:
{quote}

Buyer's descriptive criteria (id: name — how to judge):
{criteria}

Return JSON:
{{"scores": [{{"criterion_id": str, "score": 0-100, "reason": "one or two sentences citing the quote / supplier data"}}],
  "risks": [str], "points_to_confirm": [str]}}
"risks": up to 3 commercial or delivery risks in this quote. "points_to_confirm": up to 3 things the buyer
should confirm with this supplier before accepting."""
