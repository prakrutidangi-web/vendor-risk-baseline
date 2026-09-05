# Configuration and example data

## Configuration

All configuration is environment variables, loaded from a `.env` file in the project root
(copy `.env.example` to `.env` and fill in your own values). The only required variable for
a real run is `GROQ_API_KEY` (a free key from https://console.groq.com/keys, no credit card
needed). Set `DRY_RUN=true` in `.env` to run the whole pipeline offline with a canned response
instead, useful for grading this without an API key.

## Example input

`case_01_northwind_analytics/` is one complete test case: four plain-text documents describing
a fictional SaaS vendor being evaluated for a procurement decision.

- `financial_summary.md`: quarterly revenue, customer concentration, runway
- `security_questionnaire.md`: encryption, MFA, incident response, breach notification, SOC 2
- `contract_draft.md`: liability cap, indemnification, breach notification SLA, termination terms
- `reference_notes.md`: a customer reference call

This case is deliberately adversarial: on the surface the vendor looks strong (revenue growing,
SOC 2 Type II, positive reference call), but its own security questionnaire admits there is no
documented incident response plan. Whether the baseline notices that gap is exactly what the
test case in the proposal checks.

## Example output

`expected_output/case_01_northwind_analytics_baseline_output.json` is the actual output the
baseline produced for this case on a real run against Groq (not a hypothetical or hand-written
example). Running `python run_baseline.py --input examples/case_01_northwind_analytics` again
will not reproduce this exact text byte-for-byte, since the model is called at a low but nonzero
temperature, but it should land on materially the same finding (a missing incident response plan)
and the same `approve_with_conditions` recommendation most of the time.
