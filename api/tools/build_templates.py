"""
One-off: write app/data/templates/_skeleton.json + one JSON per category template.

    python tools/build_templates.py

The skeleton is the VoltEdge RFQ structure (header, sections 1-14, annexures A-D) as
boilerplate blocks with {{slot}} placeholders. Category templates add their own
slots and the category-specific blocks the skeleton pulls in via {"t": "include"}.

Block types: title, sub, p, h1, h2, bullet, num, table{rows, header?}, include{key},
and computed tables: supply_table, cert_table, compliance_table, weights_table.
Any block may carry "if": "<slot>" — rendered only when that slot has a
meaningful value (not empty / "Not needed" / "No" / "Not required").

Every slot with data_point_ids produces a requirement when the RFQ is approved:
  req      text with {v} (slot value) and other {slot} refs
  kind     mandatory | scored    (level slots: Mandatory -> mandatory, Preferred -> scored)
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "data" / "templates"

LEVEL = ["Mandatory", "Preferred", "Not needed"]
YESNO = ["Yes", "No"]


def slot(id, label, bucket, type="text", *, options=None, default=None, ask=False,
         question=None, dp=None, req=None, kind="scored", unit=None, hint=None):
    s = {"id": id, "label": label, "bucket": bucket, "type": type}
    if options:
        s["options"] = options
    if default is not None:
        s["default"] = default
    if ask:
        s["ask"] = True
    s["question"] = question or f"{label}?"
    if dp:
        s["data_point_ids"] = dp
        s["req"] = req
        s["kind"] = kind
    if unit:
        s["unit"] = unit
    if hint:
        s["hint"] = hint
    return s


BUCKETS = [
    {"id": "header", "label": "RFQ details"},
    {"id": "technical", "label": "Technical requirements"},
    {"id": "quality", "label": "Quality (§6)"},
    {"id": "delivery", "label": "Delivery & commercial (§7–8)"},
    {"id": "org", "label": "Supplier organisation (§9)"},
    {"id": "financial", "label": "Financial capability (§10)"},
    {"id": "esg", "label": "ESG & continuity (§11–12)"},
]

# ── common slots (every template) ────────────────────────────────────────────
COMMON_SLOTS = [
    slot("buyer", "Issuing company", "header", ask=True,
         question="Which company is issuing this RFQ?", hint="Your company's registered name"),
    slot("rfq_title", "RFQ title / item", "header", ask=True,
         question="What should the RFQ be titled (the item being sourced)?",
         hint="e.g. Steel Mounting Bracket for EV Application"),
    slot("quantity", "Contract quantity", "header", "number", ask=True, unit="units",
         question="How many units do you need in total?",
         dp=["installed_capacity", "capacity_utilisation_pct"],
         req="Spare installed capacity to supply {quantity} units over {schedule_months} months"),
    slot("schedule_months", "Supply period", "header", "number", default=3, ask=True, unit="months",
         question="Over how many months should supply run?"),
    slot("issue_date", "Issue date", "header", "date", question="RFQ issue date?"),
    slot("quote_due", "Quotation due", "header", "date", question="Quotation due date?"),
    slot("contact", "RFQ contact", "header",
         question="Who is the RFQ contact? (name, designation, email)",
         hint="e.g. Priya Kulkarni, Head Supply Chain, priya@company.com"),

    slot("iso_9001", "ISO 9001 certification", "quality", "level", options=LEVEL, default="Mandatory",
         ask=True, question="ISO 9001 certification?", dp=["iso_9001", "sector_certification"],
         req="ISO 9001 certification by an accredited body"),
    slot("iatf_16949", "IATF 16949 certification", "quality", "level", options=LEVEL, default="Not needed",
         question="IATF 16949 (automotive QMS)?", dp=["sector_certification"],
         req="IATF 16949 certification or demonstrated automotive QMS maturity"),
    slot("iso_14001", "ISO 14001 environmental management", "quality", "level", options=LEVEL,
         default="Preferred", question="ISO 14001?", dp=["iso_14001", "sector_certification"],
         req="ISO 14001 environmental management certification"),
    slot("iso_45001", "ISO 45001 occupational health & safety", "quality", "level", options=LEVEL,
         default="Preferred", question="ISO 45001?", dp=["iso_45001", "sector_certification"],
         req="ISO 45001 occupational health and safety certification"),
    slot("max_rejection_pct", "Maximum rejection / rework rate", "quality", "number", default=1, unit="%",
         question="Maximum acceptable rejection / rework rate (%)?", dp=["rejection_rate_pct"],
         req="Rejection / rework rate at or below {v}% over the last 12 months"),

    slot("delivery_location", "Delivery location", "delivery", ask=True,
         question="Where should material be delivered (city / plant)?"),
    slot("delivery_model", "Delivery model", "delivery", "choice", ask=True,
         options=["JIT every 3 days", "Weekly call-offs", "Monthly lots", "Single lot"],
         question="How should deliveries be scheduled?", dp=["otd_pct"],
         req="On-time delivery performance suitable for {v} supply"),
    slot("payment_days", "Payment terms", "delivery", "choice", options=["30", "45", "60", "90"],
         default="60", unit="days", question="Payment terms (days from GRN)?",
         dp=["cash_conversion_cycle", "banking_relationships", "existing_debt"],
         req="Working capital and bank lines to carry {v}-day receivables"),
    slot("freight", "Freight", "delivery", "choice", options=["Included (FOR buyer plant)", "Ex-works"],
         default="Included (FOR buyer plant)", question="Freight basis?"),

    slot("min_years", "Minimum years in business", "org", "number", default=5, unit="years",
         question="Minimum years in business?", dp=["date_incorporation", "promoter_experience_yrs"],
         req="At least {v} years in business with experienced management"),
    slot("min_employees", "Minimum permanent workforce", "org", "number", default=20, unit="employees",
         question="Minimum permanent employees?", dp=["employees_permanent", "attrition_pct"],
         req="Stable skilled workforce of at least {v} permanent employees"),
    slot("concentration", "Customer concentration check", "org", "choice", options=YESNO, default="Yes",
         question="Check that the supplier is not over-dependent on one customer?",
         dp=["customer_concentration", "top_customers"],
         req="No excessive dependence on a single customer"),
    slot("not_blacklisted", "No blacklisting / debarment", "org", "choice", options=YESNO, default="Yes",
         question="Require a no-blacklisting declaration?", dp=["blacklisting"], kind="mandatory",
         req="Not blacklisted or debarred by any government body or customer"),

    slot("min_turnover_lakh", "Minimum annual turnover", "financial", "number", unit="₹ lakh",
         question="Minimum annual turnover (₹ lakh)?", dp=["turnover"], kind="mandatory",
         req="Annual turnover of at least ₹{v} lakh (latest FY)"),
    slot("min_current_ratio", "Minimum current ratio", "financial", "number", default=1.2,
         question="Minimum current ratio?", dp=["current_ratio"],
         req="Current ratio of at least {v}"),
    slot("positive_net_worth", "Positive net worth", "financial", "choice", options=YESNO, default="Yes",
         question="Require positive net worth?", dp=["net_worth"], kind="mandatory",
         req="Positive net worth with no material erosion"),
    slot("no_default", "No default / overdue statutory dues", "financial", "choice", options=YESNO,
         default="Yes", question="Require no loan default and no overdue statutory dues?",
         dp=["statutory_dues", "penal_interest"], kind="mandatory",
         req="No loan default, NPA, or material overdue statutory dues"),
    slot("tax_compliance", "Timely GST / ITR filing", "financial", "choice", options=YESNO, default="Yes",
         question="Check GST and ITR filing timeliness?", dp=["gst_filing_timeliness", "itr_timeliness"],
         req="Timely GST return and income-tax filings"),

    slot("esg_level", "ESG / EHS expectation", "esg", "choice",
         options=["Full ESG/EHS compliance", "Basic EHS", "Not evaluated"], default="Basic EHS",
         question="How strict should ESG / EHS evaluation be?",
         dp=["ehs_policy", "labour_violation_3y", "grievance_mechanism"],
         req="{v}: documented EHS policy, no labour-law violations, worker grievance mechanism"),
    slot("continuity", "Business continuity & insurance", "esg", "choice", options=YESNO, default="Yes",
         question="Require insurance cover and a business-continuity plan?", dp=["insurance"],
         req="Insurance coverage and business-continuity arrangements in place"),
]

# ── skeleton (VoltEdge structure) ────────────────────────────────────────────
H = lambda *cells: list(cells)  # noqa: E731

SKELETON = [
    {"t": "title", "text": "Request for Quotation"},
    {"t": "sub", "text": "{{rfq_title}}"},
    {"t": "table", "header": True, "rows": [
        H("RFQ detail", "Requirement"),
        H("Issuing company", "{{buyer}}"),
        H("RFQ reference", "{{rfq_ref}}"),
        H("Issue date", "{{issue_date}}"),
        H("Quotation due", "{{quote_due}} by 17:00 IST"),
        H("Contract quantity", "{{quantity}} units over {{schedule_months}} months"),
        H("Delivery model", "{{delivery_model}} to {{delivery_location}}"),
        H("Commercial terms", "INR, GST extra, freight {{freight}}, payment {{payment_days}} days"),
        H("RFQ contact", "{{contact}}"),
    ]},
    {"t": "p", "text": "This document invites qualified {{supplier_type}} to submit a complete technical and "
                       "commercial quotation for {{rfq_title}}. The selected supplier must demonstrate capable "
                       "manufacturing processes, stable quality systems, adequate liquidity for a "
                       "{{payment_days}}-day payment cycle, and reliable {{delivery_model}} supply."},
    {"t": "p", "text": "The released drawing, approved material specification and purchase order will prevail "
                       "over this document where expressly stated."},
    {"t": "h1", "text": "Document control"},
    {"t": "table", "header": True, "rows": [
        H("Revision", "Date", "Description", "Owner"),
        H("0", "{{issue_date}}", "RFQ issued for supplier quotation", "Strategic Sourcing"),
    ]},
    {"t": "h1", "text": "Submission instructions"},
    {"t": "num", "text": "Submit one signed PDF response and one editable commercial workbook by email to the RFQ "
                         "contact before the quotation deadline."},
    {"t": "num", "text": "Use the section numbering and response tables in this RFQ. Clearly identify every "
                         "exception, assumption and dependency in the deviation schedule."},
    {"t": "num", "text": "Quote in Indian rupees. Show material, conversion, finishing, packaging, freight, "
                         "tooling and taxes separately."},
    {"t": "num", "text": "Provide documentary evidence requested in the bid checklist. Redacted documents may be "
                         "accepted where commercially sensitive, subject to buyer review."},
    {"t": "num", "text": "Direct technical and commercial questions only to the RFQ contact."},
    {"t": "h1", "text": "RFQ contents"},
    {"t": "table", "header": True, "rows": [
        H("Section", "Topic"),
        H("1", "Purpose and sourcing context"), H("2", "Scope of supply"),
        H("3", "Component and technical requirements"), H("4", "Manufacturing process and equipment"),
        H("5", "Capacity and production readiness"), H("6", "Quality management and product assurance"),
        H("7", "Delivery logistics and packaging"), H("8", "Commercial and payment terms"),
        H("9", "Supplier organization and business health"), H("10", "Financial capability and liquidity"),
        H("11", "ESG EHS and responsible business"), H("12", "Information security and business continuity"),
        H("13", "Evaluation and award process"), H("14", "General RFQ terms"),
        H("A", "Supplier response schedules"), H("B", "Quotation and cost breakdown"),
        H("C", "Compliance matrix and declarations"), H("D", "Bid submission checklist"),
    ]},

    {"t": "h1", "text": "1 Purpose and sourcing context"},
    {"t": "p", "text": "{{buyer}} seeks a production supplier for {{rfq_title}}. {{purpose}}"},
    {"t": "p", "text": "The sourcing objective is to establish a reliable, cost-competitive and quality-controlled "
                       "supply arrangement for {{quantity}} units over an initial {{schedule_months}}-month period. "
                       "The award may be extended or scaled subject to performance and mutual agreement; no "
                       "forecast beyond the purchase order is guaranteed."},
    {"t": "h1", "text": "2 Scope of supply"},
    {"t": "include", "key": "scope"},
    {"t": "bullet", "text": "Ongoing quality control, lot traceability, change management, corrective action and "
                            "capacity reporting."},
    {"t": "bullet", "text": "Support for buyer audits, trials, cost-reduction workshops and continuous improvement."},
    {"t": "h2", "text": "2.1 Supply period and quantity"},
    {"t": "supply_table"},

    {"t": "h1", "text": "3 Component and technical requirements"},
    {"t": "h2", "text": "3.1 Indicative component definition"},
    {"t": "include", "key": "technical"},
    {"t": "h2", "text": "3.2 Drawing and specification control"},
    {"t": "bullet", "text": "The buyer will release the controlled drawing / specification to shortlisted suppliers "
                            "under confidentiality obligations."},
    {"t": "bullet", "text": "No material, source, process, tooling, location or sub-tier change is permitted after "
                            "approval without prior written buyer authorization."},
    {"t": "bullet", "text": "Supplier shall perform a manufacturing-feasibility review and identify technical "
                            "risks in the quotation."},
    {"t": "h2", "text": "3.3 Technical deliverables"},
    {"t": "include", "key": "deliverables"},

    {"t": "h1", "text": "4 Manufacturing process and equipment"},
    {"t": "p", "text": "The supplier shall own or have securely controlled access to equipment capable of "
                       "producing the item consistently at the quoted rate. All proposed outsourced processes must "
                       "be disclosed with the sub-tier name, location, certification and control method."},
    {"t": "h2", "text": "4.1 Required process capability"},
    {"t": "include", "key": "process"},

    {"t": "h1", "text": "5 Capacity and production readiness"},
    {"t": "bullet", "text": "Demonstrate capacity for {{quantity}} units over {{schedule_months}} months and at "
                            "least 20 percent short-term upside without deterioration in quality or delivery."},
    {"t": "bullet", "text": "State cycle time, planned shifts, staffing, changeover time, scrap assumption and "
                            "bottleneck operation."},
    {"t": "bullet", "text": "Identify other programmes sharing key equipment and quantify available capacity "
                            "during the proposed production window."},
    {"t": "table", "header": True, "rows": [
        H("Readiness milestone", "Supplier proposed date", "Evidence or owner"),
        H("Feasibility closure", "", ""), H("Tooling / setup complete", "", ""), H("First-off trial", "", ""),
        H("Sample / first article approval", "", ""), H("Start of production", "", ""),
        H("First delivery", "", ""),
    ]},

    {"t": "h1", "text": "6 Quality management and product assurance"},
    {"t": "h2", "text": "6.1 Management system"},
    {"t": "cert_table"},
    {"t": "h2", "text": "6.2 Inspection and performance"},
    {"t": "table", "header": True, "rows": [
        H("Control", "Expectation"),
        H("Rejection / rework", "At or below {{max_rejection_pct}}% over the last 12 months"),
        H("First-off and last-off", "Documented approval at start, after changeover, tool intervention or restart"),
        H("Final inspection", "Identity, quantity, key dimensions, appearance, marking and packaging"),
        H("Traceability", "Each lot traceable to raw-material heat / batch, production date, machine and inspection"),
    ]},
    {"t": "h2", "text": "6.3 Nonconformance and corrective action"},
    {"t": "bullet", "text": "Containment within 24 hours, initial root-cause response within three working days "
                            "and completed 8D normally within ten working days."},
    {"t": "bullet", "text": "No use-as-is, repair or rework is permitted without written concession."},

    {"t": "h1", "text": "7 Delivery logistics and packaging"},
    {"t": "table", "header": True, "rows": [
        H("Parameter", "Requirement"),
        H("Delivery location", "{{delivery_location}}; final ship-to address in purchase order"),
        H("Frequency", "{{delivery_model}}"),
        H("Delivery performance", "Target 100 percent on-time and in-full against the confirmed window"),
        H("Advance shipment notice", "Electronic ASN before dispatch with PO, part, quantity, lot and ETA"),
    ]},
    {"t": "bullet", "text": "Use packaging that prevents corrosion, deformation and damage through transport and "
                            "storage; obtain buyer approval for pack quantity and labelling."},

    {"t": "h1", "text": "8 Commercial and payment terms"},
    {"t": "table", "header": True, "rows": [
        H("Commercial item", "RFQ requirement"),
        H("Currency", "Indian rupees"),
        H("Price basis", "Firm for the initial {{schedule_months}}-month programme"),
        H("Freight", "{{freight}}"),
        H("GST and statutory taxes", "Shown separately at applicable rates"),
        H("Payment", "{{payment_days}} days from receipt of correct tax invoice and accepted goods (GRN)"),
        H("Quotation validity", "Minimum 120 days from quotation deadline"),
        H("Tooling", "One-time cost shown separately with milestone and ownership proposal"),
    ]},
    {"t": "p", "text": "The supplier shall complete Annexure B and provide a transparent cost model."},

    {"t": "h1", "text": "9 Supplier organization and business health"},
    {"t": "p", "text": "The buyer will assess whether the supplier has a stable organization capable of supporting "
                       "this programme."},
    {"t": "table", "header": True, "rows": [
        H("Assessment area", "Requirement"),
        H("Years in business", "At least {{min_years}} years"),
        H("Workforce", "At least {{min_employees}} permanent employees; attrition and skills disclosed"),
        H("Customer concentration", "Top five customer shares disclosed; no excessive single-customer dependence"),
        H("Debarment", "No blacklisting or debarment (declaration required: {{not_blacklisted}})"),
    ]},

    {"t": "h1", "text": "10 Financial capability and liquidity"},
    {"t": "p", "text": "The supplier must have adequate liquidity to purchase material, operate production and "
                       "carry receivables under a {{payment_days}}-day payment cycle."},
    {"t": "table", "header": True, "rows": [
        H("Area", "Expectation"),
        H("Turnover", "At least ₹{{min_turnover_lakh}} lakh in the latest audited year"),
        H("Liquidity", "Current ratio at least {{min_current_ratio}} and positive working capital"),
        H("Net worth", "Positive net worth required: {{positive_net_worth}}"),
        H("Defaults and statutory dues", "No default / overdue dues required: {{no_default}}"),
        H("Tax compliance", "Timely GST and ITR filings checked: {{tax_compliance}}"),
    ]},

    {"t": "h1", "text": "11 ESG EHS and responsible business"},
    {"t": "p", "text": "Evaluation level: {{esg_level}}."},
    {"t": "bullet", "text": "Maintain all required environmental consents and manage hazardous waste through "
                            "authorised handlers."},
    {"t": "bullet", "text": "Maintain risk assessments, machine guarding, PPE, training and incident reporting."},
    {"t": "bullet", "text": "Prohibit child labour, forced labour, harassment and discrimination; maintain a worker "
                            "grievance mechanism."},
    {"t": "bullet", "text": "Maintain controls against bribery, fraud and conflicts of interest."},

    {"t": "h1", "text": "12 Information security and business continuity"},
    {"t": "p", "text": "Restrict drawings, specifications and pricing to authorised personnel. Submit a site "
                       "business-continuity plan covering power failure, equipment breakdown, labour disruption "
                       "and logistics interruption, with insurance coverage (required: {{continuity}})."},

    {"t": "h1", "text": "13 Evaluation and award process"},
    {"t": "weights_table"},
    {"t": "p", "text": "Mandatory requirements and unacceptable risk may override aggregate score. The buyer may "
                       "conduct clarification meetings, plant audits, sample trials and financial diligence."},

    {"t": "h1", "text": "14 General RFQ terms"},
    {"t": "num", "text": "This RFQ is an invitation to quote and does not constitute a purchase order or "
                         "obligation to award business."},
    {"t": "num", "text": "The buyer may accept or reject any response, negotiate with one or more suppliers, "
                         "modify or cancel the RFQ, or divide the award."},
    {"t": "num", "text": "No deviation is effective unless expressly accepted in the purchase order."},
    {"t": "num", "text": "The supplier shall comply with applicable Indian laws and regulatory requirements."},
    {"t": "num", "text": "Proposed subcontracting requires disclosure and does not relieve the supplier of "
                         "responsibility for quality, delivery, compliance or confidentiality."},

    {"t": "h1", "text": "Annexure A Supplier response schedules"},
    {"t": "h2", "text": "A1 Supplier identity and contacts"},
    {"t": "table", "header": True, "rows": [H("Field", "Response")] + [
        H(f, "Supplier response") for f in [
            "Legal company name", "Registered office", "Manufacturing site proposed", "Udyam / CIN",
            "GSTIN", "Year established", "Ownership type", "Primary RFQ contact", "Quality contact",
            "Finance contact"]]},
    {"t": "h2", "text": "A2 Organization and experience"},
    {"t": "table", "header": True, "rows": [H("Question", "Supplier response and evidence reference")] + [
        H(q, "") for q in [
            "Describe relevant experience in {{supplier_type}}.",
            "List programmes of comparable complexity completed in the last five years.",
            "Provide top five customers and approximate percentage of annual sales.",
            "State current permanent and contract headcount, shifts and attrition.",
            "Disclose material litigation, regulatory notices, debarment or insolvency matters."]]},
    {"t": "h2", "text": "A3 Customer references"},
    {"t": "table", "header": True, "rows": [
        H("Customer", "Item or process", "Annual volume", "Supply period", "Reference contact"),
        H("", "", "", "", ""), H("", "", "", "", ""), H("", "", "", "", "")]},
    {"t": "h2", "text": "A4 Manufacturing equipment"},
    {"t": "include", "key": "equipment"},
    {"t": "h2", "text": "A5 Inspection and testing equipment"},
    {"t": "include", "key": "gauges"},
    {"t": "h2", "text": "A6 Proposed manufacturing route"},
    {"t": "table", "header": True, "rows": [
        H("Step", "Operation", "Machine or source", "Key controls", "In-house or sub-tier")] + [
        H(str(i), "", "", "", "") for i in range(1, 7)]},
    {"t": "h2", "text": "A7 Capacity and delivery plan"},
    {"t": "table", "header": True, "rows": [H("Capacity input", "Supplier response")] + [
        H(x, "") for x in [
            "Installed capacity (units/month)", "Current utilisation", "Planned output for this RFQ",
            "Maximum output with 20 percent surge", "Expected scrap and rework percentage",
            "Transport mode and transit time"]]},
    {"t": "h2", "text": "A8 Certification and quality performance"},
    {"t": "table", "header": True, "rows": [H("Item", "Certificate / metric", "Evidence attached")] + [
        H(x, "", "Yes or No") for x in [
            "ISO 9001", "IATF 16949", "ISO 14001", "ISO 45001", "BIS / product certification",
            "Customer PPM for latest 12 months", "On-time delivery for latest 12 months"]]},
    {"t": "h2", "text": "A9 Financial information"},
    {"t": "table", "header": True, "rows": [H("Metric INR lakh", "FY 2023-24", "FY 2024-25", "FY 2025-26")] + [
        H(x, "", "", "") for x in [
            "Revenue", "EBITDA", "Profit after tax", "Net worth", "Total debt", "Current ratio",
            "Debt equity", "Interest coverage", "Receivable days"]]},
    {"t": "h2", "text": "A10 ESG EHS and ethics questionnaire"},
    {"t": "table", "header": True, "rows": [H("Question", "Yes No NA", "Details and evidence")] + [
        H(x, "", "") for x in [
            "Are all environmental and operating consents valid for the proposed site",
            "Are hazardous materials and waste managed through authorized channels",
            "Have any fatalities, major injuries or regulatory notices occurred in the last three years",
            "Is there a worker grievance mechanism with non-retaliation protection",
            "Are anti-bribery and whistleblowing controls in place"]]},
    {"t": "h2", "text": "A11 Business continuity"},
    {"t": "table", "header": True, "rows": [H("Topic", "Supplier response")] + [
        H(x, "") for x in [
            "Recovery time for bottleneck operation", "Alternate site or equipment",
            "Critical sub-tier dependency and backup source", "Insurance types, limits and validity"]]},

    {"t": "h1", "text": "Annexure B Quotation and cost breakdown"},
    {"t": "h2", "text": "B1 Unit price quotation"},
    {"t": "include", "key": "cost"},
    {"t": "h2", "text": "B2 Material and productivity assumptions"},
    {"t": "include", "key": "assumptions"},
    {"t": "h2", "text": "B3 One-time costs"},
    {"t": "table", "header": True, "rows": [
        H("Item", "Amount INR", "Lead time", "Ownership")] + [
        H(x, "", "", "") for x in ["Tooling / dies / patterns", "Fixtures and gauges",
                                   "Development and trials", "Other"]]},
    {"t": "h2", "text": "B4 Commercial summary"},
    {"t": "table", "header": True, "rows": [H("Field", "Response")] + [
        H(x, "Supplier response") for x in [
            "Quoted delivered unit price before GST", "Total value for {{quantity}} units before GST",
            "Total one-time cost", "Quotation validity", "Payment terms accepted or deviation", "MOQ"]]},

    {"t": "h1", "text": "Annexure C Compliance matrix and declarations"},
    {"t": "h2", "text": "C1 Requirement compliance"},
    {"t": "compliance_table"},
    {"t": "h2", "text": "C2 Deviation schedule"},
    {"t": "p", "text": "List every technical, commercial, timing, quality, logistics or legal deviation. If blank, "
                       "the supplier is deemed to have quoted without deviation."},
    {"t": "table", "header": True, "rows": [
        H("RFQ section", "Requirement", "Supplier deviation", "Reason", "Proposed alternative")] + [
        H("", "", "", "", "") for _ in range(4)]},
    {"t": "h2", "text": "C3 Supplier declaration"},
    {"t": "p", "text": "We confirm that the information submitted is complete and accurate; that we have disclosed "
                       "all material assumptions and deviations; and that we understand this RFQ does not create "
                       "an obligation on {{buyer}} to place an order."},
    {"t": "table", "header": True, "rows": [H("Field", "Response")] + [
        H(x, "Supplier response") for x in ["Authorized signatory name", "Designation", "Company",
                                            "Signature", "Date", "Company seal"]]},

    {"t": "h1", "text": "Annexure D Bid submission checklist"},
    {"t": "table", "header": True, "rows": [H("No", "Submission item", "Attached", "Document reference")] + [
        H(str(i + 1), x, "Yes or No", "") for i, x in enumerate([
            "Signed RFQ cover and supplier declaration", "Completed compliance and deviation schedules",
            "Process flow and feasibility review", "Equipment list relevant to proposed line",
            "Capacity calculation and delivery plan", "ISO / product certificates as applicable",
            "Latest customer quality and delivery performance", "Audited financial statements for three years",
            "Organization chart and programme team", "Customer references",
            "ESG EHS and ethics questionnaire with evidence", "Unit price cost breakdown and one-time costs",
            "All subcontractors and special-process sources disclosed"])]},
]



def tbl(*rows):
    return {"t": "table", "header": True, "rows": [list(r) for r in rows]}


def equip(rows):
    return [tbl(("Equipment", "Make model and year", "Capacity or accuracy", "Quantity", "Owned or outsourced"),
                *[(r, "", "", "", "") for r in rows])]


def gauges(rows):
    return [tbl(("Gauge or equipment", "Range / accuracy", "Quantity", "Calibration status"),
                *[(r, "", "", "") for r in rows])]


def cost(rows):
    return [tbl(("Cost element", "INR per unit", "Basis or assumption"),
                *[(r, "", "") for r in rows + ["Packaging", "Freight to buyer plant", "Overheads", "Profit",
                                               "Delivered unit price before GST", "GST rate"]])]


def assumptions(rows):
    return [tbl(("Input", "Supplier value", "Notes"), *[(r, "", "") for r in rows])]


# ── category templates ───────────────────────────────────────────────────────
TEMPLATES = [
    {
        "id": "sheet_metal",
        "name": "Sheet-metal pressed / bent part",
        "description": "Pressed, bent, laser-cut or stamped steel/aluminium parts and brackets (VoltEdge format).",
        "keywords": ["bracket", "sheet metal", "pressing", "stamping", "bending", "laser cutting", "CRCA",
                     "pressed part", "enclosure", "panel"],
        "supplier_type": "sheet metal and precision-engineering suppliers",
        "purpose": "The part is formed from sheet and finished to the released drawing.",
        "defaults": {"iatf_16949": "Preferred", "min_turnover_lakh": 300},
        "weights": [("Technical feasibility process and equipment", 25),
                    ("Quality system and performance", 20),
                    ("Commercial competitiveness and cost transparency", 20),
                    ("Capacity, delivery and readiness", 15), ("Financial health and liquidity", 10),
                    ("Organization, ESG and continuity", 10)],
        "slots": [
            slot("part_desc", "Component description", "technical", ask=True,
                 question="Briefly describe the part and where it is used."),
            slot("material", "Material grade", "technical", "choice", ask=True,
                 options=["CRCA IS 513 DD", "HR IS 1079", "Galvanised GI IS 277", "SS 304", "Aluminium 5052"],
                 question="Material grade?", dp=["hsn_products"],
                 req="Proven production in {v} sheet / strip"),
            slot("thickness_mm", "Nominal thickness", "technical", "number", ask=True, unit="mm",
                 question="Nominal sheet thickness (mm)?"),
            slot("processes", "Manufacturing route", "technical", "multi", ask=True,
                 options=["Laser cutting", "Blanking", "Pressing", "Bending", "CNC machining", "Welding"],
                 default=["Laser cutting", "Pressing", "Bending"],
                 question="Which processes are needed?", dp=["key_machinery", "inhouse_vs_outsourced"],
                 kind="mandatory", req="In-house equipment for {v}"),
            slot("finish", "Surface finish", "technical", "choice", ask=True,
                 options=["Zinc plating + trivalent passivation", "Powder coating", "ED coating", "None"],
                 question="Surface finish?", dp=["inhouse_vs_outsourced"],
                 req="Surface treatment ({v}) in-house or through a controlled sub-tier"),
            slot("ppap", "Sample approval", "technical", "choice",
                 options=["PPAP Level 3", "PPAP Level 2", "First article inspection only"],
                 default="PPAP Level 3", question="Sample / part approval level?",
                 dp=["testing_equipment", "quality_policy"],
                 req="{v} with APQP core tools and calibrated dimensional / coating inspection"),
            slot("sector", "Sector experience", "technical", "choice",
                 options=["Automotive / EV", "Electrical & power", "Railways", "General engineering"],
                 default="Automotive / EV", question="Which industry experience should the supplier have?",
                 dp=["approved_vendor_oems", "client_reference", "repeat_business_pct"],
                 req="Proven supply track record to {v} customers"),
        ],
        "blocks": {
            "scope": [{"t": "bullet", "text": x} for x in [
                "Procurement of approved raw material ({{material}}) and full material traceability.",
                "Tooling, fixtures, gauges and process development for {{processes}} and inspection.",
                "Trial samples, dimensional reports and {{ppap}} documentation.",
                "Serial production, surface protection ({{finish}}), packaging and delivery to the buyer plant."]],
            "technical": [tbl(("Attribute", "Indicative requirement"),
                              ("Component", "{{part_desc}}"),
                              ("Material", "{{material}} or drawing-approved equivalent"),
                              ("Nominal thickness", "{{thickness_mm}} mm, subject to released drawing"),
                              ("Manufacturing route", "{{processes}}, deburring, surface treatment and final inspection"),
                              ("Surface finish", "{{finish}}"),
                              ("Appearance", "Free from sharp edges, burrs, cracks, rust, dents, distortion and coating damage"),
                              ("Part marking", "Supplier code, tool identification, batch code and date traceability"))],
            "deliverables": [tbl(("Deliverable", "Minimum requirement", "Timing"),
                                 ("Feasibility review", "Signed review covering material, tooling, tolerances, route and capacity", "With quotation"),
                                 ("Process flow", "End-to-end flow including outsourced operations", "With quotation"),
                                 ("Trial samples", "From intended process and tooling", "Before approval"),
                                 ("Part approval", "{{ppap}}", "Before production shipment"),
                                 ("Certificates", "Material test certificate, coating report and certificate of conformity", "Each lot"))],
            "process": [tbl(("Process area", "Expected capability", "Evidence required"),
                            ("Material preparation", "Sheet storage, identification, blanking or laser cutting", "Equipment list and traceability flow"),
                            ("Pressing", "Suitable press tonnage, die setting, guarding and poka-yoke", "Press details and utilization"),
                            ("Bending", "CNC press brake with back-gauge and tooling", "Machine details and calibration"),
                            ("Machining", "CNC VMC / drilling for drawing-controlled features", "Machine capability and fixtures"),
                            ("Surface treatment", "{{finish}} with thickness, adhesion and corrosion controls", "Approved source and test plan"),
                            ("Inspection", "Calibrated dimensional, visual and coating inspection", "Gauge list and calibration status"))],
            "equipment": equip(["Presses", "CNC press brakes", "Laser or blanking equipment", "CNC VMC or machining centres",
                                "Deburring and finishing", "Surface treatment"]),
            "gauges": gauges(["CMM or vision system", "Height gauge and surface plate", "Coating thickness gauge",
                              "Salt spray access"]),
            "cost": cost(["Steel input at gross weight", "Scrap credit", "Blanking or laser cutting", "Pressing and bending",
                          "Machining", "Surface treatment", "Inspection and testing"]),
            "assumptions": assumptions(["Material grade and source", "Material thickness", "Gross / net weight per part",
                                        "Material yield percentage", "Pressing cycle time", "Quoted production batch"]),
        },
    },
    {
        "id": "cnc_machined",
        "name": "CNC machined component",
        "description": "Turned / milled precision components, shafts, housings, flanges.",
        "keywords": ["CNC", "machined", "turning", "milling", "VMC", "shaft", "housing", "flange", "bush", "precision"],
        "supplier_type": "CNC machining and precision-engineering suppliers",
        "purpose": "The component is machined to tight tolerances from bar, forging or casting stock.",
        "defaults": {"min_turnover_lakh": 200},
        "weights": [("Technical capability and tolerances", 30), ("Quality system and inspection", 25),
                    ("Commercial competitiveness", 20), ("Capacity and delivery", 10),
                    ("Financial health", 10), ("Organization and ESG", 5)],
        "slots": [
            slot("part_desc", "Component description", "technical", ask=True,
                 question="Briefly describe the component and its application."),
            slot("material", "Material", "technical", "choice", ask=True,
                 options=["EN8 / EN9 steel", "EN19 / EN24 alloy steel", "SS 304 / 316", "Aluminium 6061", "Brass"],
                 question="Material?", dp=["hsn_products"], req="Experience machining {v}"),
            slot("tolerance", "Tightest tolerance", "technical", "choice", ask=True,
                 options=["±0.01 mm", "±0.02 mm", "±0.05 mm", "±0.1 mm"],
                 question="Tightest dimensional tolerance?", dp=["key_machinery"], kind="mandatory",
                 req="CNC turning / VMC capacity capable of holding {v}"),
            slot("features", "Critical features", "technical", ask=True,
                 question="Any critical features (bores, threads, surface finish Ra)?"),
            slot("heat_treatment", "Heat treatment", "technical", "choice",
                 options=["None", "Hardening & tempering", "Case carburising", "Induction hardening"],
                 default="None", question="Heat treatment?", dp=["inhouse_vs_outsourced"],
                 req="Controlled heat-treatment route ({v})"),
            slot("finish", "Surface finish / coating", "technical", "choice",
                 options=["As machined", "Zinc plating", "Black oxide", "Anodising"], default="As machined",
                 question="Finish / coating?"),
            slot("inspection", "Inspection capability", "technical", "choice",
                 options=["CMM required", "Conventional gauges acceptable"], default="CMM required",
                 question="Inspection capability needed?", dp=["testing_equipment"],
                 req="Inspection equipment: {v}"),
            slot("sector", "Sector experience", "technical", "choice",
                 options=["Automotive / EV", "Electrical & power", "Railways", "Defence", "General engineering"],
                 default="General engineering", question="Which industry experience should the supplier have?",
                 dp=["approved_vendor_oems", "client_reference"], req="Proven supply track record to {v} customers"),
        ],
        "blocks": {
            "scope": [{"t": "bullet", "text": x} for x in [
                "Procurement of {{material}} stock with mill test certificates.",
                "CNC machining to drawing including {{features}}.",
                "Heat treatment ({{heat_treatment}}) and finishing ({{finish}}) where specified.",
                "Inspection reports, packaging and delivery to the buyer plant."]],
            "technical": [tbl(("Attribute", "Indicative requirement"), ("Component", "{{part_desc}}"),
                              ("Material", "{{material}}"), ("Tightest tolerance", "{{tolerance}}"),
                              ("Critical features", "{{features}}"), ("Heat treatment", "{{heat_treatment}}"),
                              ("Finish", "{{finish}}"), ("Inspection", "{{inspection}}"))],
            "deliverables": [tbl(("Deliverable", "Minimum requirement", "Timing"),
                                 ("Feasibility review", "Tolerance and process capability review", "With quotation"),
                                 ("First article inspection", "Full dimensional report", "Before production"),
                                 ("Certificates", "MTC, heat-treatment report, certificate of conformity", "Each lot"))],
            "process": [tbl(("Process area", "Expected capability", "Evidence required"),
                            ("Turning", "CNC turning centres with bar feeders", "Machine list"),
                            ("Milling", "VMC / HMC with 4th axis where required", "Machine list and fixtures"),
                            ("Grinding", "Cylindrical / surface grinding for {{tolerance}} features", "Machine details"),
                            ("Inspection", "{{inspection}}", "Gauge list and calibration status"))],
            "equipment": equip(["CNC turning centres", "VMC / HMC", "Grinding machines", "Drilling / tapping",
                                "Heat treatment (if in-house)"]),
            "gauges": gauges(["CMM", "Bore gauges", "Thread gauges", "Surface roughness tester", "Hardness tester"]),
            "cost": cost(["Raw material", "Turning", "Milling", "Grinding", "Heat treatment", "Finishing",
                          "Inspection"]),
            "assumptions": assumptions(["Material and source", "Input weight per part", "Cycle time per operation",
                                        "Batch size"]),
        },
    },
    {
        "id": "fasteners",
        "name": "Fasteners",
        "description": "Bolts, nuts, screws, studs, washers — standard or special fasteners.",
        "keywords": ["bolt", "nut", "screw", "fastener", "stud", "washer", "M10", "M12", "hex", "rivet"],
        "supplier_type": "fastener manufacturers",
        "purpose": "Fasteners shall conform to the stated standard, property class and coating.",
        "defaults": {"min_turnover_lakh": 150},
        "weights": [("Conformance to standard and testing", 30), ("Quality system", 20),
                    ("Commercial competitiveness", 25), ("Capacity and delivery", 15),
                    ("Financial health", 5), ("Organization and ESG", 5)],
        "slots": [
            slot("fastener_type", "Fastener type", "technical", ask=True,
                 question="What fasteners (e.g. hex bolts, nuts, studs) and sizes?",
                 hint="e.g. M10 x 40 hex bolts"),
            slot("standard", "Standard", "technical", "choice", ask=True,
                 options=["IS 1364 / IS 1367", "DIN 933 / 931", "ISO 4014 / 4017", "ASME B18"],
                 question="Which standard?"),
            slot("property_class", "Property class / grade", "technical", "choice", ask=True,
                 options=["4.6", "8.8", "10.9", "12.9", "SS A2-70"],
                 question="Property class / grade?", dp=["testing_equipment"],
                 req="In-house mechanical testing (hardness, proof load) for property class {v}"),
            slot("coating", "Coating", "technical", "choice", ask=True,
                 options=["Zinc plated", "Hot-dip galvanised", "Geomet / zinc flake", "Black oxide", "Plain"],
                 question="Coating?", dp=["inhouse_vs_outsourced"], req="Controlled coating route ({v})"),
            slot("manufacturing", "Manufacturing route", "technical", "multi",
                 options=["Cold forging / heading", "Hot forging", "Thread rolling", "Machining", "Heat treatment"],
                 default=["Cold forging / heading", "Thread rolling", "Heat treatment"],
                 question="Required manufacturing processes?", dp=["key_machinery"],
                 req="In-house {v} capacity"),
            slot("bis", "BIS certification", "technical", "level", options=LEVEL, default="Preferred",
                 question="BIS certification for the fastener standard?", dp=["bis_cert", "sector_certification"],
                 req="BIS certification for the quoted standard"),
            slot("sector", "Sector experience", "technical", "choice",
                 options=["Automotive / EV", "Electrical & power", "Railways", "General engineering"],
                 default="General engineering", question="Which industry experience should the supplier have?",
                 dp=["approved_vendor_oems", "client_reference"], req="Proven supply track record to {v} customers"),
        ],
        "blocks": {
            "scope": [{"t": "bullet", "text": x} for x in [
                "Manufacture and supply of {{fastener_type}} to {{standard}}, property class {{property_class}}.",
                "Coating: {{coating}}; heat treatment and testing per standard.",
                "Lot-wise test certificates, packaging and delivery to the buyer plant."]],
            "technical": [tbl(("Attribute", "Indicative requirement"), ("Fastener", "{{fastener_type}}"),
                              ("Standard", "{{standard}}"), ("Property class", "{{property_class}}"),
                              ("Coating", "{{coating}}"), ("Manufacturing route", "{{manufacturing}}"),
                              ("BIS certification", "{{bis}}"))],
            "deliverables": [tbl(("Deliverable", "Minimum requirement", "Timing"),
                                 ("Test certificates", "Hardness, proof load, tensile, coating thickness", "Each lot"),
                                 ("Samples", "Initial samples with full test report", "Before production"))],
            "process": [tbl(("Process area", "Expected capability", "Evidence required"),
                            ("Heading / forging", "Cold or hot forging matched to size range", "Machine list"),
                            ("Threading", "Thread rolling with gauge control", "Thread gauges"),
                            ("Heat treatment", "Controlled hardening & tempering for class {{property_class}}", "Furnace records"),
                            ("Testing", "Hardness, proof-load and tensile testing", "Lab equipment list"))],
            "equipment": equip(["Cold headers / forging presses", "Thread rolling machines", "Heat treatment furnace",
                                "Plating / coating line"]),
            "gauges": gauges(["Universal testing machine", "Hardness tester", "Thread ring / plug gauges",
                              "Coating thickness gauge"]),
            "cost": cost(["Wire rod / bar input", "Forging / heading", "Threading", "Heat treatment", "Coating",
                          "Testing"]),
            "assumptions": assumptions(["Wire rod grade and source", "Weight per 1000 pcs", "Batch size"]),
        },
    },
    {
        "id": "castings_forgings",
        "name": "Castings / forgings",
        "description": "Sand / investment / die castings and open / closed-die forgings, with or without machining.",
        "keywords": ["casting", "forging", "foundry", "die cast", "investment casting", "SG iron", "grey iron",
                     "forged", "pattern"],
        "supplier_type": "foundries and forging suppliers",
        "purpose": "The part is produced by casting or forging and finished to the released drawing.",
        "defaults": {"min_turnover_lakh": 300},
        "weights": [("Process capability and metallurgy", 30), ("Quality, NDT and testing", 25),
                    ("Commercial competitiveness", 20), ("Capacity and delivery", 10),
                    ("Financial health", 10), ("Organization and ESG", 5)],
        "slots": [
            slot("part_desc", "Component description", "technical", ask=True,
                 question="Briefly describe the cast / forged part."),
            slot("process", "Process", "technical", "choice", ask=True,
                 options=["Sand casting", "Investment casting", "Pressure die casting", "Closed-die forging",
                          "Open-die forging"],
                 question="Casting or forging process?", dp=["key_machinery"], kind="mandatory",
                 req="In-house {v} facility"),
            slot("material", "Material grade", "technical", ask=True,
                 question="Material grade (e.g. SG 500/7, FG 260, EN8, C45)?", dp=["hsn_products"],
                 req="Proven production in {v}"),
            slot("weight_kg", "Part weight", "technical", "number", ask=True, unit="kg",
                 question="Approximate part weight (kg)?"),
            slot("machining", "Machining required", "technical", "choice", options=YESNO, default="Yes",
                 question="Is machining required?", dp=["inhouse_vs_outsourced"],
                 req="Machining in-house or through a controlled sub-tier (required: {v})"),
            slot("ndt", "NDT", "technical", "multi", options=["UT", "MPI", "Radiography", "Dye penetrant"],
                 default=["MPI"], question="Which NDT methods are required?", dp=["testing_equipment"],
                 req="NDT and metallurgical testing capability ({v})"),
            slot("sector", "Sector experience", "technical", "choice",
                 options=["Automotive / EV", "Electrical & power", "Railways", "Defence", "General engineering"],
                 default="General engineering", question="Which industry experience should the supplier have?",
                 dp=["approved_vendor_oems", "client_reference"], req="Proven supply track record to {v} customers"),
        ],
        "blocks": {
            "scope": [{"t": "bullet", "text": x} for x in [
                "Pattern / die development and {{process}} of {{material}}.",
                "Heat treatment, fettling and machining (required: {{machining}}).",
                "NDT ({{ndt}}), chemical and mechanical testing, packaging and delivery."]],
            "technical": [tbl(("Attribute", "Indicative requirement"), ("Component", "{{part_desc}}"),
                              ("Process", "{{process}}"), ("Material", "{{material}}"),
                              ("Weight", "{{weight_kg}} kg approx."), ("Machining", "{{machining}}"),
                              ("NDT", "{{ndt}}"))],
            "deliverables": [tbl(("Deliverable", "Minimum requirement", "Timing"),
                                 ("Methoding / simulation", "Gating or die design review", "Before tooling"),
                                 ("First article", "Dimensional, chemical, mechanical and NDT report", "Before production"),
                                 ("Certificates", "Heat-wise chemistry and mechanical properties", "Each lot"))],
            "process": [tbl(("Process area", "Expected capability", "Evidence required"),
                            ("Melting / heating", "Induction furnace or forging furnace with temperature control", "Equipment list"),
                            ("Moulding / forging", "{{process}} line sized for {{weight_kg}} kg parts", "Line details"),
                            ("Testing", "Spectrometer, UTM, hardness, NDT ({{ndt}})", "Lab equipment list"))],
            "equipment": equip(["Furnaces", "Moulding line / forging hammer or press", "Fettling and shot blasting",
                                "Machining centres"]),
            "gauges": gauges(["Spectrometer", "Universal testing machine", "NDT equipment", "CMM / gauges"]),
            "cost": cost(["Metal at poured / input weight", "Melting / forging conversion", "Fettling / trimming",
                          "Heat treatment", "Machining", "NDT and testing"]),
            "assumptions": assumptions(["Material grade", "Poured / input weight", "Yield percentage", "Batch size"]),
        },
    },
    {
        "id": "fabrication",
        "name": "Fabricated structures",
        "description": "Welded steel structures, frames, skids, tanks, enclosures and supports.",
        "keywords": ["fabrication", "fabricated", "welded", "structure", "frame", "skid", "tank", "steel structure",
                     "chassis", "platform"],
        "supplier_type": "structural fabrication suppliers",
        "purpose": "The structure is fabricated and welded to the released drawings and welding procedure.",
        "defaults": {"min_turnover_lakh": 300},
        "weights": [("Fabrication and welding capability", 30), ("Quality and inspection", 20),
                    ("Commercial competitiveness", 20), ("Capacity and delivery", 15),
                    ("Financial health", 10), ("Organization and ESG", 5)],
        "slots": [
            slot("part_desc", "Structure description", "technical", ask=True,
                 question="Briefly describe the structure (type, approximate size)."),
            slot("material", "Material", "technical", "choice", ask=True,
                 options=["MS IS 2062 E250", "MS IS 2062 E350", "SS 304", "Aluminium"],
                 question="Material?", dp=["hsn_products"], req="Fabrication experience in {v}"),
            slot("weight_t", "Weight per unit", "technical", "number", ask=True, unit="tonnes",
                 question="Approximate weight per unit (tonnes)?", dp=["key_machinery"], kind="mandatory",
                 req="Fabrication bay, cranes and welding equipment for {v}-tonne structures"),
            slot("welding_std", "Welding standard", "technical", "choice", ask=True,
                 options=["IS 816", "AWS D1.1", "ISO 3834", "EN 15085 (rail)"],
                 question="Welding standard?", dp=["sector_certification"],
                 req="Qualified welders and WPS/PQR to {v}"),
            slot("painting", "Surface protection", "technical", "choice",
                 options=["Epoxy primer + PU finish", "Hot-dip galvanising", "Primer only", "None"],
                 default="Epoxy primer + PU finish", question="Painting / surface protection?",
                 dp=["inhouse_vs_outsourced"], req="Surface protection ({v}) in-house or controlled sub-tier"),
            slot("inspection", "Inspection", "technical", "multi",
                 options=["Visual + dimensional", "DPT", "UT of butt welds", "Third-party inspection"],
                 default=["Visual + dimensional", "DPT"], question="Inspection requirements?",
                 dp=["testing_equipment"], req="Weld inspection capability ({v})"),
            slot("sector", "Sector experience", "technical", "choice",
                 options=["Electrical & power", "Railways", "Infrastructure", "Automotive / EV", "General engineering"],
                 default="General engineering", question="Which industry experience should the supplier have?",
                 dp=["approved_vendor_oems", "client_reference"], req="Proven supply track record to {v} customers"),
        ],
        "blocks": {
            "scope": [{"t": "bullet", "text": x} for x in [
                "Procurement of {{material}} with mill test certificates.",
                "Cutting, fit-up and welding to {{welding_std}}.",
                "Surface protection ({{painting}}), inspection ({{inspection}}), packing and delivery."]],
            "technical": [tbl(("Attribute", "Indicative requirement"), ("Structure", "{{part_desc}}"),
                              ("Material", "{{material}}"), ("Weight per unit", "{{weight_t}} tonnes"),
                              ("Welding standard", "{{welding_std}}"), ("Surface protection", "{{painting}}"),
                              ("Inspection", "{{inspection}}"))],
            "deliverables": [tbl(("Deliverable", "Minimum requirement", "Timing"),
                                 ("WPS / PQR / WPQ", "Qualified to {{welding_std}}", "With quotation"),
                                 ("Inspection test plan", "Stage-wise ITP", "Before fabrication"),
                                 ("Dossier", "MTCs, weld and paint reports, dimensional report", "Each unit"))],
            "process": [tbl(("Process area", "Expected capability", "Evidence required"),
                            ("Cutting", "CNC plasma / oxy-fuel / bandsaw", "Machine list"),
                            ("Welding", "MIG / SAW with qualified welders", "Welder qualification records"),
                            ("Handling", "EOT cranes adequate for {{weight_t}} t", "Crane capacity"),
                            ("Painting", "{{painting}}", "Paint booth / galvanising source"))],
            "equipment": equip(["CNC plasma / profile cutting", "Welding machines", "EOT cranes", "Bending / rolling",
                                "Shot blasting and paint booth"]),
            "gauges": gauges(["DPT kits", "UT flaw detector", "DFT gauge", "Measuring tapes / laser trackers"]),
            "cost": cost(["Steel at gross weight", "Cutting and fit-up", "Welding", "Surface preparation and painting",
                          "Inspection"]),
            "assumptions": assumptions(["Material grade and source", "Gross / net weight", "Welding consumables",
                                        "Man-hours per unit"]),
        },
    },
    {
        "id": "transformer",
        "name": "Transformer / electrical equipment",
        "description": "Distribution / power transformers, CTs/PTs and similar electrical equipment.",
        "keywords": ["transformer", "kVA", "distribution transformer", "DT", "CT", "PT", "switchgear",
                     "electrical equipment", "DISCOM", "11kV", "33kV"],
        "supplier_type": "transformer and electrical-equipment manufacturers",
        "purpose": "The equipment shall be designed, manufactured and type-tested to the stated standards.",
        "defaults": {"min_turnover_lakh": 300, "iso_14001": "Not needed", "iso_45001": "Not needed",
                     "delivery_model": "Monthly lots", "payment_days": "90"},
        "weights": [("Technical compliance and type tests", 30), ("Quality and certifications", 20),
                    ("Commercial competitiveness", 25), ("Capacity and delivery", 10),
                    ("Financial health", 10), ("Organization and ESG", 5)],
        "slots": [
            slot("rating_kva", "Rating", "technical", "number", ask=True, unit="kVA",
                 question="Transformer rating (kVA)?"),
            slot("voltage", "Voltage ratio", "technical", "choice", ask=True,
                 options=["11 kV / 433 V", "33 kV / 433 V", "33 kV / 11 kV"], question="Voltage ratio?"),
            slot("cooling", "Cooling", "technical", "choice", options=["ONAN", "ONAF"], default="ONAN",
                 question="Cooling type?"),
            slot("standard", "Standard", "technical", "choice", ask=True,
                 options=["IS 1180 (Part 1)", "IS 2026", "IEC 60076"], question="Design standard?",
                 dp=["key_machinery", "hsn_products"], kind="mandatory",
                 req="In-house winding, core-building and tanking facility for {rating_kva} kVA units to {v}"),
            slot("efficiency", "Energy efficiency level", "technical", "choice",
                 options=["BEE Level 2", "BEE Level 3", "Not specified"], default="BEE Level 2",
                 question="Energy efficiency level?"),
            slot("bis", "BIS certification", "technical", "level", options=LEVEL, default="Mandatory",
                 question="BIS certification?", dp=["bis_cert", "sector_certification"],
                 req="Valid BIS licence for the quoted transformer standard"),
            slot("type_test", "Type-test reports", "technical", "choice",
                 options=["CPRI / NABL type-tested design", "Routine tests only"],
                 default="CPRI / NABL type-tested design", question="Type-test requirement?",
                 dp=["testing_equipment", "completion_cert"],
                 req="{v} and in-house routine-test lab"),
            slot("utility_exp", "Utility supply experience", "technical", "choice", options=YESNO, default="Yes",
                 question="Require prior supply to DISCOMs / utilities?",
                 dp=["approved_vendor_oems", "rev_govt_pct", "client_reference"],
                 req="Prior supply to DISCOMs / utilities with completion certificates"),
        ],
        "blocks": {
            "scope": [{"t": "bullet", "text": x} for x in [
                "Design, manufacture and supply of {{rating_kva}} kVA, {{voltage}}, {{cooling}} transformers to {{standard}}.",
                "Type-test reports ({{type_test}}) and routine tests on every unit.",
                "Packing, transport, unloading at site and guarantee support."]],
            "technical": [tbl(("Attribute", "Indicative requirement"), ("Rating", "{{rating_kva}} kVA"),
                              ("Voltage ratio", "{{voltage}}"), ("Cooling", "{{cooling}}"),
                              ("Standard", "{{standard}}"), ("Energy efficiency", "{{efficiency}}"),
                              ("BIS", "{{bis}}"), ("Type tests", "{{type_test}}"))],
            "deliverables": [tbl(("Deliverable", "Minimum requirement", "Timing"),
                                 ("GTP and drawings", "Guaranteed technical particulars and GA drawing", "With quotation"),
                                 ("Type-test reports", "{{type_test}}", "With quotation"),
                                 ("Routine test reports", "Every unit", "Before dispatch"))],
            "process": [tbl(("Process area", "Expected capability", "Evidence required"),
                            ("Winding", "HV / LV winding machines", "Machine list"),
                            ("Core building", "CRGO slitting / cutting and core building", "Facility details"),
                            ("Drying and tanking", "Vapour-phase or oven drying, oil filtration", "Equipment list"),
                            ("Testing", "Routine-test lab per {{standard}}", "Lab calibration certificates"))],
            "equipment": equip(["Winding machines", "Core cutting / building", "Drying oven / VPD", "Oil filtration plant",
                                "Tank fabrication"]),
            "gauges": gauges(["Transformer test bench", "Loss measurement kit", "Insulation resistance tester",
                              "Oil BDV test set"]),
            "cost": cost(["CRGO / amorphous core", "Copper / aluminium winding", "Transformer oil", "Tank and fittings",
                          "Labour and testing"]),
            "assumptions": assumptions(["Core and conductor material", "No-load / load losses", "Weight of core and coil"]),
        },
    },
]


# What the supplier must already make. Every template gets a mandatory "product line" requirement,
# checked against the CSV data points NIC codes / HSN products / key machinery, so an MSME in the
# wrong line is rejected at the gate (with a reason) rather than filtered out silently.
PRODUCT_LINE = {
    "sheet_metal": "sheet-metal pressed / bent / laser-cut parts",
    "cnc_machined": "CNC machined components",
    "fasteners": "fasteners (bolts, nuts, studs, screws)",
    "castings_forgings": "castings or forgings",
    "fabrication": "fabricated / welded steel structures",
    "transformer": "transformers or similar electrical equipment",
}


def product_line_slot(tid: str) -> dict:
    line = PRODUCT_LINE[tid]
    return slot("product_line", "Supplier already makes this product", "technical", "choice", options=YESNO,
                default="Yes", question=f"Must the supplier already manufacture {line}?",
                dp=["key_machinery", "nic_codes", "hsn_products"], kind="mandatory",
                req=f"Already manufactures {line} (NIC codes / product range / machinery)")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for t in TEMPLATES:
        if not any(x["id"] == "product_line" for x in t["slots"]):
            t["slots"].insert(0, product_line_slot(t["id"]))
    (OUT / "_skeleton.json").write_text(json.dumps(
        {"buckets": BUCKETS, "common_slots": COMMON_SLOTS, "blocks": SKELETON}, indent=1, ensure_ascii=False),
        "utf-8")
    for t in TEMPLATES:
        (OUT / f"{t['id']}.json").write_text(json.dumps(t, indent=1, ensure_ascii=False), "utf-8")
    # base .docx (styles/header/footer) for rendering
    src = ROOT.parents[1] / "VoltEdge_RFQ_Sheet_Metal_EV_Bracket.docx"
    if src.exists():
        shutil.copy(src, OUT / "base.docx")
    print(f"wrote skeleton + {len(TEMPLATES)} templates to {OUT}")


if __name__ == "__main__":
    main()
