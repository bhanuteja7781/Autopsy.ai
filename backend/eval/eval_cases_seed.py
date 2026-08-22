import uuid
import datetime
from backend.core.db import db

SEED_EVAL_CASES = [
    # 1. PM-KISAN: Landholding eligibility reversal (Silent Contradiction)
    {
        "claim_a_excerpt": "Under PM-KISAN, financial assistance of Rs 6,000 per year is restricted exclusively to small and marginal landholder farmer families with cultivable landholding up to 2 hectares.",
        "claim_b_excerpt": "All landholding eligible farmer families irrespective of the size of their landholdings are covered under PM-KISAN scheme.",
        "claim_type": "eligibility",
        "human_label": "silent_contradiction",
        "notes": "PM-KISAN expanded coverage to all farmers without citing the initial 2-hectare limitation in standard communications."
    },
    # 2. PM-KISAN: Payment Installment Schedule (Consistent)
    {
        "claim_a_excerpt": "The benefit shall be transferred directly into the bank accounts of beneficiaries in three equal four-monthly installments of Rs 2,000 each.",
        "claim_b_excerpt": "The payment is credited directly into verified bank accounts in three tranches of Rs 2,000 every four months.",
        "claim_type": "amount",
        "human_label": "consistent",
        "notes": "Lexical variance with identical financial benefit schedule."
    },
    # 3. PM-KISAN: e-KYC Mandatory Deadline (Explicit Update)
    {
        "claim_a_excerpt": "e-KYC is optional for receiving PM-KISAN installments for the first fiscal year.",
        "claim_b_excerpt": "As per revised guidelines dated May 2022, e-KYC is mandatory for all PM-KISAN registered farmers, superseding previous exemption rules.",
        "claim_type": "deadline",
        "human_label": "explicit_update",
        "notes": "Explicit policy amendment superseding previous rules."
    },
    # 4. Ayushman Bharat: Coverage Ceiling (Consistent)
    {
        "claim_a_excerpt": "PM-JAY provides health insurance coverage of up to Rs 5,00,000 per family per year for secondary and tertiary care hospitalization.",
        "claim_b_excerpt": "Under Ayushman Bharat, each eligible family receives cashless inpatient healthcare benefits capped at 5 lakh rupees annually.",
        "claim_type": "amount",
        "human_label": "consistent",
        "notes": "Exact match with minor phrasing difference."
    },
    # 5. Ayushman Bharat: Senior Citizen 70+ Expansion (Explicit Update)
    {
        "claim_a_excerpt": "PM-JAY benefits are strictly determined by deprivation and occupational criteria as per the Socio-Economic and Caste Census (SECC) 2011 database.",
        "claim_b_excerpt": "The Union Cabinet has approved the expansion of Ayushman Bharat PM-JAY to provide health coverage to all senior citizens aged 70 years and above irrespective of their income or SECC status.",
        "claim_type": "eligibility",
        "human_label": "explicit_update",
        "notes": "Explicitly announced policy expansion for 70+ age demographic."
    },
    # 6. Aadhaar-PAN Linking: Late Penalty Fee (Silent Contradiction)
    {
        "claim_a_excerpt": "PAN cards can be linked with Aadhaar free of cost through the e-filing portal before the stipulated deadline.",
        "claim_b_excerpt": "Linking of PAN with Aadhaar requires payment of a non-refundable fee of Rs 1,000 under Section 234H.",
        "claim_type": "amount",
        "human_label": "silent_contradiction",
        "notes": "Fee changed from zero to Rs 1,000 without inline justification in portal instructions."
    },
    # 7. OpenAI API ToS: Training on API Customer Data (Explicit Update)
    {
        "claim_a_excerpt": "OpenAI may use content submitted to the Services, including API inputs and completions, to develop and improve our models.",
        "claim_b_excerpt": "Effective March 1, 2023, OpenAI will not use data submitted by customers via our API to train or improve our models unless you explicitly opt in.",
        "claim_type": "other",
        "human_label": "explicit_update",
        "notes": "Explicitly dated policy reversal regarding API data usage."
    },
    # 8. GitHub Free Tier: Private Repository Collaboration Limits (Explicit Update)
    {
        "claim_a_excerpt": "GitHub Free accounts may create unlimited private repositories with up to 3 collaborators.",
        "claim_b_excerpt": "Announcing GitHub Free now includes unlimited private repositories with unlimited collaborators, superseding the 3-collaborator limit.",
        "claim_type": "coverage",
        "human_label": "explicit_update",
        "notes": "Explicit feature update removing collaborator restrictions."
    },
    # 9. Google Workspace: Unlimited Storage Guarantee (Silent Contradiction)
    {
        "claim_a_excerpt": "G Suite Enterprise provides unlimited Google Drive cloud storage for organizations with 5 or more users.",
        "claim_b_excerpt": "Google Workspace Enterprise Standard includes 5 TB of pooled cloud storage per user.",
        "claim_type": "coverage",
        "human_label": "silent_contradiction",
        "notes": "Unlimited storage capped to 5 TB per user without explicit grandfathering acknowledgement in product briefs."
    },
    # 10. Twitter/X API: Academic Research Access Tier (Silent Contradiction)
    {
        "claim_a_excerpt": "The Academic Research product track provides free access to the full Twitter archive for academic researchers and university institutions.",
        "claim_b_excerpt": "Access to Twitter API v2 endpoints requires subscribing to the Pro tier starting at $5,000 per month.",
        "claim_type": "amount",
        "human_label": "silent_contradiction",
        "notes": "Free academic access tier discontinued without cross-referencing past research grants."
    },
    # 11. National Scholarship Scheme: Minimum CGPA Requirement (Consistent)
    {
        "claim_a_excerpt": "Applicants must secure at least 60% marks or equivalent grade in the previous final qualifying examination.",
        "claim_b_excerpt": "A minimum aggregate score of 60% or corresponding GPA in the qualifying degree is mandatory for scholarship consideration.",
        "claim_type": "eligibility",
        "human_label": "consistent",
        "notes": "Identical grade requirement expressed with alternative academic phrasing."
    },
    # 12. PMAY-Urban: Subsidized Interest Rates (Explicit Update)
    {
        "claim_a_excerpt": "Beneficiaries under CLSS for MIG-I category are eligible for an interest subsidy of 4.0% for a tenure of 20 years.",
        "claim_b_excerpt": "The Credit Linked Subsidy Scheme (CLSS) for MIG categories has been formally discontinued effective March 31, 2021.",
        "claim_type": "deadline",
        "human_label": "explicit_update",
        "notes": "Formal sunset clause explicitly communicated."
    },
    # 13. PM Ujjwala Yojana: Cylinder Subsidy Count (Silent Contradiction)
    {
        "claim_a_excerpt": "PMUY provides 12 subsidized domestic LPG refill cylinders per financial year to enrolled BPL households.",
        "claim_b_excerpt": "Ujjwala beneficiaries are entitled to targeted subsidy for up to 9 domestic 14.2 kg LPG cylinders annually.",
        "claim_type": "coverage",
        "human_label": "silent_contradiction",
        "notes": "Subsidized cylinder quota reduced from 12 to 9 without referencing earlier quota."
    },
    # 14. EPFO: PF Withdrawal Minimum Service Duration (Consistent)
    {
        "claim_a_excerpt": "Continuous service of 5 years or more under an EPFO registered establishment is required for tax-free PF balance withdrawal.",
        "claim_b_excerpt": "No income tax is deducted on PF withdrawals if the employee has rendered five continuous years of service.",
        "claim_type": "eligibility",
        "human_label": "consistent",
        "notes": "Equivalent tax exemption conditions."
    },
    # 15. Student Visa Proof of Funds Requirement (Silent Contradiction)
    {
        "claim_a_excerpt": "International students must show proof of living expenses of at least CAD 10,000 for the first study year.",
        "claim_b_excerpt": "Effective January 1, 2024, the cost-of-living financial requirement for study permit applicants is CAD 20,635.",
        "claim_type": "amount",
        "human_label": "explicit_update",
        "notes": "Explicit policy increase indexed to cost of living."
    },
    # 16. FastTag Toll Exemption (Insufficient Evidence)
    {
        "claim_a_excerpt": "Local residents living within 20 km of the toll plaza may apply for a discounted monthly toll pass.",
        "claim_b_excerpt": "Commercial transport vehicles must install valid AIS-140 compliant GPS tracking systems.",
        "claim_type": "other",
        "human_label": "insufficient_evidence",
        "notes": "Unrelated clauses that cannot be logically compared for contradiction."
    },
    # 17. RBI Tokenization Mandate: Storage of Card on File (Explicit Update)
    {
        "claim_a_excerpt": "Payment aggregators and merchants may store customer debit and credit card 16-digit numbers in their databases.",
        "claim_b_excerpt": "In accordance with RBI circular DPSS.CO.PD.No.834, with effect from October 1, 2022, no entity in the card transaction chain other than card issuers shall store actual card data (CoF).",
        "claim_type": "other",
        "human_label": "explicit_update",
        "notes": "Explicit statutory regulatory mandate prohibiting card storage."
    },
    # 18. Crop Insurance Scheme: Claim Settlement Window (Silent Contradiction)
    {
        "claim_a_excerpt": "Under PMFBY, all crop insurance claims must be assessed and settled by insurance companies within 21 days of crop harvest data submission.",
        "claim_b_excerpt": "Insurance claim settlements shall be processed within 45 working days following state government subsidy release.",
        "claim_type": "deadline",
        "human_label": "silent_contradiction",
        "notes": "Settlement SLA relaxed from 21 days to 45 working days without citing previous turnaround timeline."
    },
    # 19. WhatsApp Privacy Policy: Metadata Sharing with Facebook (Explicit Update)
    {
        "claim_a_excerpt": "Respect for your privacy is coded into our DNA. We do not share your account information or phone number with Facebook.",
        "claim_b_excerpt": "As part of the Facebook family of companies, WhatsApp receives information from, and shares information with, this family of companies to improve services and ads.",
        "claim_type": "other",
        "human_label": "explicit_update",
        "notes": "Updated privacy policy disclosing data sharing with parent entity."
    },
    # 20. Free Higher Education Scheme: Parental Income Cap (Silent Contradiction)
    {
        "claim_a_excerpt": "The fee waiver scheme covers undergraduate students whose annual family gross income from all sources does not exceed Rs 2.5 Lakhs.",
        "claim_b_excerpt": "Tuition fee waiver is applicable for students with parental annual income capped at Rs 1.8 Lakhs per annum.",
        "claim_type": "eligibility",
        "human_label": "silent_contradiction",
        "notes": "Income eligibility threshold lowered from 2.5L to 1.8L without explanation."
    },
    # 21. Cloud Hosting: Free Tier Monthly Bandwidth (Silent Contradiction)
    {
        "claim_a_excerpt": "Free Tier tier includes 100 GB of outbound bandwidth per month at no extra charge.",
        "claim_b_excerpt": "Outbound data transfer for Free Tier accounts is limited to 20 GB per billing cycle.",
        "claim_type": "amount",
        "human_label": "silent_contradiction",
        "notes": "Bandwidth quota reduced from 100 GB to 20 GB silently."
    }
]

def seed_eval_cases():
    conn = db.get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT count(*) as cnt FROM eval_cases")
    count = cur.fetchone()["cnt"]
    
    if count == 0:
        for case in SEED_EVAL_CASES:
            case_id = str(uuid.uuid4())
            cur.execute("""
            INSERT INTO eval_cases (id, claim_a_excerpt, claim_b_excerpt, claim_type, human_label, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                case_id,
                case["claim_a_excerpt"],
                case["claim_b_excerpt"],
                case["claim_type"],
                case["human_label"],
                case["notes"],
                datetime.datetime.utcnow().isoformat()
            ))
        conn.commit()
    conn.close()

if __name__ == "__main__":
    seed_eval_cases()
    print(f"Seeded {len(SEED_EVAL_CASES)} eval cases successfully.")
