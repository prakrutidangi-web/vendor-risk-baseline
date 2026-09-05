"""The single prompt this baseline runs. Kept in its own file so the exact
instruction given to the model is easy to read and audit on its own,
separate from the plumbing in llm.py and baseline.py.
"""

BASELINE_PROMPT = """You are a vendor risk analyst. You've been given four documents about a vendor: a
financial summary, a security questionnaire, a contract excerpt, and reference-call notes. Read all four
and write a one-page vendor risk brief for a procurement lead, covering financial health, security
posture, contract terms, and reference feedback, ending with a clear recommendation (approve / approve
with conditions / reject or escalate).

FINANCIAL SUMMARY:
{financial_text}

SECURITY QUESTIONNAIRE:
{security_text}

CONTRACT EXCERPT:
{contract_text}

REFERENCE NOTES:
{reference_text}

Return JSON with this exact shape:
{{
  "memo": "<full markdown risk brief, structured with an Executive Summary, Top Concerns, and Recommendation>",
  "identified_issues": ["<short id-like label for each distinct problem you found, e.g. 'revenue_decline'>", ...],
  "recommendation": "<'approve' | 'approve_with_conditions' | 'reject_or_escalate'>"
}}"""
