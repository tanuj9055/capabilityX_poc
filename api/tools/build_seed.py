"""
One-off: build app/data/catalog.json + app/data/sellers.json (the seller pool: the real
MSMEs in the two source CSVs) from the CSVs in the QistonPe root.

    python tools/build_seed.py  [--src <dir containing the CSVs>]

The catalog is the fixed vocabulary every RFQ requirement is mapped onto. It is
hand-defined below (ids are stable), mirroring the survey columns (A–F) and the
MetalCapital / OpportunityX data points. Values are kept as the raw text the CSVs
hold — the matcher (Gemini) reads them as-is; only mechanical fixes are applied:
  * cp1252 decode (en/em dashes), lost ₹ symbols restored, "?" arrows -> "→"
  * Remi + Transcore columns are shifted up by one row in rows 1–8 of the
    MetalCapital sheet (legal form sits in the header row) — realigned here.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "data"

CATEGORIES = [
    {"id": "org", "label": "Organisation Structure & Health"},
    {"id": "policy", "label": "Policies & Practices"},
    {"id": "ops", "label": "Operations – Technical Capacity"},
    {"id": "fin", "label": "Financial Details"},
    {"id": "cert", "label": "Certifications"},
    {"id": "cust", "label": "Customer Concentration & Revenue Mix"},
]

# (id, category, label, source)
CATALOG = [
    # ── A. Organisation structure & health ──
    ("legal_structure", "org", "Legal structure", "MetalCapital · Udyam"),
    ("date_incorporation", "org", "Date of incorporation", "MetalCapital · Udyam"),
    ("date_commencement", "org", "Date of commencement", "MetalCapital · Udyam"),
    ("nic_codes", "org", "NIC codes (industry classification)", "MetalCapital · Udyam"),
    ("enterprise_class", "org", "Enterprise classification (Micro/Small/Medium)", "MetalCapital · Udyam"),
    ("promoter_experience_yrs", "org", "Promoter / key management experience (yrs)", "Survey"),
    ("employees_permanent", "org", "Employees – permanent", "Survey"),
    ("employees_contract", "org", "Employees – contract/casual", "Survey"),
    ("attrition_pct", "org", "Annual attrition rate (%)", "Survey"),
    ("succession_plan", "org", "Succession plan in place", "Survey"),
    ("group_companies", "org", "Group / associate companies", "Survey"),
    ("org_chart", "org", "Organisation chart available", "Survey"),
    # ── B. Policies & practices ──
    ("quality_policy", "policy", "Documented quality policy", "Survey"),
    ("hr_policy", "policy", "Documented HR policy", "Survey"),
    ("ehs_policy", "policy", "Documented EHS / safety policy", "Survey"),
    ("internal_audit_freq", "policy", "Internal audit frequency", "Survey"),
    ("grievance_mechanism", "policy", "Grievance / whistle-blower mechanism", "Survey"),
    ("labour_violation_3y", "policy", "Labour law violation (last 3 yrs)", "Survey"),
    ("posh_compliance", "policy", "POSH compliance", "Survey"),
    ("itr_timeliness", "policy", "ITR filing timeliness", "MetalCapital · ITR"),
    ("statutory_dues", "policy", "Statutory dues not deposited on time", "MetalCapital · ITR"),
    ("gst_filing_timeliness", "policy", "GST return filing timeliness", "MetalCapital · GST"),
    ("blacklisting", "policy", "Blacklisting / debarment declaration", "OpportunityX"),
    # ── C. Operations – technical capacity ──
    ("key_machinery", "ops", "Key machinery / equipment", "Survey"),
    ("installed_capacity", "ops", "Installed capacity (units/month)", "Survey"),
    ("capacity_utilisation_pct", "ops", "Current capacity utilisation (%)", "Survey"),
    ("otd_pct", "ops", "On-time delivery % (last 12m)", "Survey"),
    ("rejection_rate_pct", "ops", "Rejection / rework rate % (last 12m)", "Survey"),
    ("inventory_turns", "ops", "Inventory turns (per year)", "Survey"),
    ("rm_lead_time_days", "ops", "Raw material lead time (days)", "Survey"),
    ("inhouse_vs_outsourced", "ops", "In-house vs outsourced processes", "Survey"),
    ("testing_equipment", "ops", "Testing / gauging equipment", "Survey"),
    ("electricity_consumption", "ops", "Monthly electricity consumption trend", "MetalCapital · Electricity bill"),
    ("load_utilisation", "ops", "Electrical load utilisation %", "MetalCapital · Electricity bill"),
    ("sanctioned_load", "ops", "Sanctioned electricity load", "MetalCapital · Electricity bill"),
    ("hsn_products", "ops", "HSN-wise product breakdown", "MetalCapital · GST"),
    ("largest_order", "ops", "Largest order fulfilled", "OpportunityX · Past POs"),
    # ── D. Financial details ──
    ("turnover", "fin", "Turnover (latest FY)", "MetalCapital · Audited financials"),
    ("income_trend", "fin", "Multi-year income trend", "MetalCapital · ITR"),
    ("yoy_growth", "fin", "YoY turnover growth and margin trend", "MetalCapital · Form 3CD"),
    ("monthly_turnover_gst", "fin", "Monthly turnover trend (GSTR-3B)", "MetalCapital · GSTR-3B"),
    ("net_worth", "fin", "Net worth", "MetalCapital · Audited financials"),
    ("current_ratio", "fin", "Current ratio", "MetalCapital · CAM"),
    ("quick_ratio", "fin", "Quick ratio", "MetalCapital · CAM"),
    ("debt_equity", "fin", "Debt-equity ratio", "MetalCapital · Audited financials"),
    ("tol_tnw", "fin", "TOL/TNW ratio", "MetalCapital · Audited financials"),
    ("interest_coverage", "fin", "Interest coverage ratio", "MetalCapital · Audited financials"),
    ("ebitda_margin", "fin", "EBITDA margin %", "MetalCapital · Audited financials"),
    ("gross_profit_pct", "fin", "Gross profit %", "MetalCapital · Form 3CD"),
    ("net_profit_pct", "fin", "Net profit %", "MetalCapital · Form 3CD"),
    ("rota", "fin", "Return on total assets", "MetalCapital · Audited financials"),
    ("stock_days", "fin", "Stock holding period (days)", "MetalCapital · Audited financials"),
    ("debtor_days", "fin", "Debtors collection period (days)", "MetalCapital · Audited financials"),
    ("creditor_days", "fin", "Creditors payment period (days)", "MetalCapital · Audited financials"),
    ("cash_conversion_cycle", "fin", "Cash conversion cycle", "MetalCapital · CAM"),
    ("debit_credit_ratio", "fin", "Bank debit-to-credit ratio", "MetalCapital · Bank statements"),
    ("high_value_txn", "fin", "High-value transaction flags", "MetalCapital · Bank statements"),
    ("penal_interest", "fin", "Penal interest / cheque returns", "MetalCapital · Bank statements"),
    ("existing_debt", "fin", "Existing debt obligations", "MetalCapital · Bank statements"),
    ("itc_utilisation", "fin", "GST ITC utilisation pattern", "MetalCapital · GSTR-3B"),
    ("cd_note_ratio", "fin", "Credit/debit note ratio", "MetalCapital · GST"),
    ("banking_relationships", "fin", "Banking relationships", "Survey"),
    ("collateral", "fin", "Collateral / security available", "Survey"),
    ("planned_capex", "fin", "Planned capex – next 12m", "Survey"),
    ("insurance", "fin", "Insurance coverage in place", "Survey"),
    # ── E. Certifications ──
    ("iso_9001", "cert", "ISO 9001", "OpportunityX"),
    ("iso_14001", "cert", "ISO 14001", "OpportunityX"),
    ("iso_45001", "cert", "ISO 45001 / OHSAS 18001", "OpportunityX"),
    ("bis_cert", "cert", "BIS certificate", "OpportunityX"),
    ("sector_certification", "cert", "Sector-specific certifications", "Survey"),
    ("approved_vendor_oems", "cert", "Customer-approved vendor status (OEMs)", "Survey"),
    ("cert_in_process", "cert", "Certification currently under process", "Survey"),
    ("certs_renewed_12m", "cert", "Certifications renewed in last 12m", "Survey"),
    ("completion_cert", "cert", "Completion certificates", "OpportunityX"),
    ("local_content_cert", "cert", "Local content self-certificate", "OpportunityX"),
    ("mii_class", "cert", "MII class (Class I / II)", "OpportunityX"),
    ("local_content_pct", "cert", "Declared local content %", "OpportunityX"),
    ("dpiit_startup", "cert", "DPIIT startup certificate", "OpportunityX"),
    ("zed_level", "cert", "ZED certification level", "OpportunityX"),
    # ── F. Customer concentration & revenue mix ──
    ("rev_oem_pct", "cust", "Revenue split – OEM (%)", "Survey"),
    ("rev_govt_pct", "cust", "Revenue split – Government/PSU (%)", "Survey"),
    ("rev_jobwork_pct", "cust", "Revenue split – job-work (%)", "Survey"),
    ("largest_customer_years", "cust", "Years – relationship with largest customer", "Survey"),
    ("repeat_business_pct", "cust", "% repeat business (last 12m)", "Survey"),
    ("export_pct", "cust", "Export revenue (%)", "Survey"),
    ("customer_concentration", "cust", "Customer concentration", "MetalCapital · Bank statements"),
    ("top_customers", "cust", "Top customers and suppliers", "MetalCapital · CAM"),
    ("recurring_vendors", "cust", "Recurring vendor pattern", "MetalCapital · Bank statements"),
    ("client_reference", "cust", "Client reference letters", "OpportunityX"),
]

# Survey column header (prefix, before " *") -> catalog id
SURVEY_COLS = {
    "Promoter / Key Management Experience (yrs)": "promoter_experience_yrs",
    "Employees – Permanent": "employees_permanent",
    "Employees – Contract/Casual": "employees_contract",
    "Annual Attrition Rate (%)": "attrition_pct",
    "Succession Plan in Place?": "succession_plan",
    "Group / Associate Companies?": "group_companies",
    "Organisation Chart Available?": "org_chart",
    "Documented Quality Policy?": "quality_policy",
    "Documented HR Policy?": "hr_policy",
    "Documented EHS / Safety Policy?": "ehs_policy",
    "Internal Audit Frequency": "internal_audit_freq",
    "Grievance / Whistle-blower Mechanism?": "grievance_mechanism",
    "Labour Law Violation (Last 3 Yrs)?": "labour_violation_3y",
    "POSH Compliance (if applicable)?": "posh_compliance",
    "Key Machinery / Equipment (list)": "key_machinery",
    "Installed Capacity (units/month)": "installed_capacity",
    "Current Capacity Utilisation (%)": "capacity_utilisation_pct",
    "On-Time Delivery % (last 12m)": "otd_pct",
    "Rejection / Rework Rate % (last 12m)": "rejection_rate_pct",
    "Inventory Turns (per year)": "inventory_turns",
    "Raw Material Lead Time (days)": "rm_lead_time_days",
    "In-House vs Outsourced Processes": "inhouse_vs_outsourced",
    "Testing / Gauging Equipment Available?": "testing_equipment",
    "Number of Banking Relationships": "banking_relationships",
    "Collateral / Security Available?": "collateral",
    "Planned Capex – Next 12m (? Lakh)": "planned_capex",
    "Insurance Coverage in Place?": "insurance",
    "Sector-Specific Certification (specify)": "sector_certification",
    "Customer-Approved Vendor Status (list OEMs)": "approved_vendor_oems",
    "Any Certification Currently Under Process?": "cert_in_process",
    "Certifications Renewed in Last 12m?": "certs_renewed_12m",
    "Revenue Split – OEM (%)": "rev_oem_pct",
    "Revenue Split – Government/PSU (%)": "rev_govt_pct",
    "Revenue Split – Job-Work (%)": "rev_jobwork_pct",
    "Years – Relationship w/ Largest Customer": "largest_customer_years",
    "% Repeat Business (last 12m)": "repeat_business_pct",
    "Export Revenue (%)": "export_pct",
}

# MetalCapital / OpportunityX sheet: "Sr No." -> catalog id (aligned columns)
MC_ROWS = {
    2: "legal_structure", 3: "date_incorporation", 4: "date_commencement", 5: "nic_codes",
    6: "enterprise_class",
    7: "high_value_txn", 8: "penal_interest", 9: "debit_credit_ratio",
    10: "customer_concentration", 11: "recurring_vendors", 12: "existing_debt",
    13: "itr_timeliness", 14: "income_trend", 15: "statutory_dues",
    16: "electricity_consumption", 17: "load_utilisation", 18: "sanctioned_load",
    19: "tol_tnw", 20: "debt_equity", 21: "net_worth", 22: "rota", 23: "interest_coverage",
    24: "ebitda_margin", 25: "turnover", 26: "stock_days", 27: "debtor_days",
    28: "creditor_days", 29: "yoy_growth", 30: "gross_profit_pct", 31: "net_profit_pct",
    32: "monthly_turnover_gst", 33: "itc_utilisation", 34: "top_customers",
    35: "cash_conversion_cycle", 36: "current_ratio", 37: "quick_ratio", 38: "cd_note_ratio",
    39: "hsn_products", 40: "gst_filing_timeliness",
    41: "blacklisting", 42: "bis_cert", 43: "iso_9001", 44: "iso_14001", 45: "iso_45001",
    46: "largest_order", 47: "completion_cert", 48: "client_reference", 49: "local_content_cert",
    50: "mii_class", 51: "local_content_pct", 52: "dpiit_startup", 53: "zed_level",
}
# Remi + Transcore: rows 1..7 hold the values of rows 2..8 (shift by one).
# The "Sr No." of the header row is "Column1"; we treat it as row 1.
SHIFTED_ROWS = {1: "legal_structure", 2: "date_incorporation", 3: "date_commencement", 4: "nic_codes",
                5: "enterprise_class", 6: "high_value_txn", 7: "penal_interest"}

REFERENCE = {
    # csv column -> (seller id, display name, survey "Customer Name", profile, city, category, line)
    # city only where the source data states it; category = closest RFQ template.
    # Only the 4 MSMEs present in BOTH CSVs. Left out: Mahalaxmi Vidyut Udyog, Maxxi Centerprises and
    # Juhi Electricals (only the OpportunityX rows 41-53 filled, ~12 values) and the survey's sample
    # row "Sundar Precision Components" (QP-0001, not in the data-points sheet).
    "Remi": ("ref-remi", "Remi", "Remi",
             "Distribution transformer manufacturer (Bhopal); supplies DISCOMs (MPPKVVCL).",
             "Bhopal", "transformer", "Distribution transformers"),
    "Gurunank": ("ref-gurunanak", "Gurunanak Engineering", "Gurunanak Engineering",
                 "Fabricated metal products / machining job shop; BHEL vendor.",
                 None, "fabrication", "Fabrication & machining job shop"),
    "KCS": ("ref-kcs", "KCS Fasteners", "KCS Fastners",
            "Fasteners, forging/pressing/stamping and machined parts; BHEL vendor.",
            None, "fasteners", "Fasteners, forging & stamping"),
    "Transcore": ("ref-transcore", "Transcore", "Transcore",
                  "Current/instrument transformer manufacturer; BHEL Bhopal vendor.",
                  "Bhopal", "transformer", "Current / instrument transformers"),
}


def clean(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip().strip(".").strip()
    if not v or v in {"---"}:
        return None
    v = re.sub(r"\?(?=\s?\d)", "₹", v)          # lost rupee symbol
    v = re.sub(r"\s\?\s", " → ", v)              # lost arrow
    return re.sub(r"\s+", " ", v)


def read_csv(path: Path) -> list[list[str]]:
    text = path.read_bytes().decode("cp1252")
    return [r for r in csv.reader(io.StringIO(text))]


def build(src: Path) -> None:
    catalog = {
        "categories": CATEGORIES,
        "data_points": [
            {"id": i, "category": c, "label": l, "source": s} for i, c, l, s in CATALOG
        ],
    }
    ids = {d["id"] for d in catalog["data_points"]}

    # ── MetalCapital / OpportunityX sheet ──
    mc = read_csv(src / "MSME Data Points(Customers).csv")
    header = mc[0]
    by_sr: dict[int, list[str]] = {}
    for r in mc[1:]:
        if not r or not r[0].strip():
            continue
        sr = 1 if r[0].strip() == "Column1" else int(r[0]) if r[0].strip().isdigit() else None
        if sr:
            by_sr[sr] = r

    sellers: dict[str, dict] = {}
    for col, (sid, name, _, profile, city, category, line) in REFERENCE.items():
        ci = header.index(col)
        values: dict[str, str] = {}
        shifted = col in {"Remi", "Transcore"}
        for sr, dp in MC_ROWS.items():
            if shifted and sr <= 8:
                continue
            v = clean(by_sr.get(sr, [None] * len(header))[ci])
            if v and v != "No" or (v == "No" and sr >= 41):
                values[dp] = v
        if shifted:
            for sr, dp in SHIFTED_ROWS.items():
                v = clean(by_sr[sr][ci])
                if v:
                    values[dp] = re.sub(r"\.\d$", "", v)  # "Partnership firm.2" (dup header)
        sellers[col] = {
            "id": sid, "name": name, "source": "csv", "profile": profile,
            "city": city or "—", "category": category, "category_label": line, "values": values,
        }

    # ── Survey sheet ──
    sv = read_csv(src / "Capability_Graph_Gap_Survey(Survey).csv")
    # the CSV headers use an em dash ("Employees — Permanent"); the keys above use an en dash
    cols = [c.replace(" *", "").replace("—", "–").strip() for c in sv[1]]
    survey_name_to_col = {v[2]: k for k, v in REFERENCE.items() if v[2]}
    for r in sv[2:]:
        if len(r) < 2 or r[1].strip() not in survey_name_to_col:
            continue
        s = sellers[survey_name_to_col[r[1].strip()]]
        for i, c in enumerate(cols):
            dp = SURVEY_COLS.get(c)
            v = clean(r[i]) if i < len(r) else None
            if dp and v:
                s["values"][dp] = v

    out = list(sellers.values())
    order = [d["id"] for d in catalog["data_points"]]
    for s in out:
        bad = set(s["values"]) - ids
        assert not bad, (s["id"], bad)
        s["values"] = {k: s["values"].get(k) for k in order}  # every data point; None = not on record

    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "catalog.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False), "utf-8")
    (DATA / "sellers.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), "utf-8")
    print(f"catalog: {len(catalog['data_points'])} data points")
    for s in out:
        print(f"  {s['id']:16s} {sum(v is not None for v in s['values'].values()):3d}/{len(order)} values on record")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT.parents[1]))
    build(Path(ap.parse_args().src))
