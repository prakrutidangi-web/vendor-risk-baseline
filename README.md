# Vendor Risk Diligence Agent: Capstone Baseline

CSE 598 Agentic AI capstone proposal baseline, submitted by Prakruti Dangi. This repository
contains only the minimal single-prompt baseline described in the proposal, not the improved
multi-agent system planned for later phases of the project.

## What this does

Given four documents about a vendor (a financial summary, a security questionnaire, a contract
excerpt, and reference-call notes), the baseline sends all four to a single LLM call and asks it
to write a one-page vendor risk brief with a recommendation (approve / approve with conditions /
reject or escalate). No decomposition, no tools, no verification step: this is the simplest
reasonable starting point, used to measure how much a later, more structured system improves on
it.

## Dependencies

Python 3.11 or newer. Pinned packages, listed in `requirements.txt`:

- `openai==3.6.0` (used only as an HTTP client against Groq's OpenAI-compatible endpoint)
- `python-dotenv==1.0.1`
- `tenacity==9.1.4`

## Setup

```bash
git clone <this-repo-url>
cd vendor-risk-baseline
python3 -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## Required API keys / environment variables

Open `.env` and set `GROQ_API_KEY` to a free key from https://console.groq.com/keys (no credit
card required). Everything else in `.env` already has a safe default:

| Variable | Purpose | Default |
|---|---|---|
| `GROQ_API_KEY` | Groq API key (required for a real run) | *(none, must be set)* |
| `GROQ_MODEL` | Primary model | `openai/gpt-oss-120b` |
| `GROQ_FALLBACK_MODELS` | Comma-separated fallback models if the primary is unavailable | see `.env.example` |
| `GROQ_BASE_URL` | Groq's OpenAI-compatible endpoint | `https://api.groq.com/openai/v1` |
| `LLM_RPM_LIMIT` | Client-side requests-per-minute cap | `25` |
| `LLM_MAX_RETRIES` | Retry attempts on transient errors | `5` |
| `LLM_DAILY_SAFETY_CAP` | Client-side max requests per day | `900` |
| `DRY_RUN` | `true` to skip the API entirely and return a canned response | `false` |

## Exact command to run it

```bash
python run_baseline.py --input examples/case_01_northwind_analytics
```

This prints the model's JSON response to stdout and also writes it to
`output/case_01_northwind_analytics_output.json`.

To try it with no API key at all (offline, canned response, useful for grading without a key):

```bash
DRY_RUN=true python run_baseline.py --input examples/case_01_northwind_analytics
```

## Input and output locations

- **Input:** `examples/case_01_northwind_analytics/` — four plain-text documents describing one
  fictional SaaS vendor being evaluated for a procurement decision:
  - `financial_summary.md`: quarterly revenue, customer concentration, runway
  - `security_questionnaire.md`: encryption, MFA, incident response, breach notification, SOC 2
  - `contract_draft.md`: liability cap, indemnification, breach notification SLA, termination terms
  - `reference_notes.md`: a customer reference call

  This case is deliberately adversarial: on the surface the vendor looks strong (revenue growing,
  SOC 2 Type II, positive reference call), but its own security questionnaire admits there is no
  documented incident response plan. Whether the baseline notices that gap is exactly what this
  test case checks.

- **Output:** printed to stdout and written to `output/case_01_northwind_analytics_output.json`.
  `examples/expected_output/case_01_northwind_analytics_baseline_output.json` is the actual output
  the baseline produced for this case on a real run against Groq (not a hypothetical or
  hand-written example), and
  `examples/expected_output/case_01_northwind_analytics_baseline_output_screenshot.png` is a
  screenshot of that same run's terminal output, showing the baseline running successfully and
  producing output. Running the command again will not reproduce that exact text byte-for-byte,
  since the model is called at a low but nonzero temperature, but it should land on materially the
  same finding (a missing incident response plan) and the same `approve_with_conditions`
  recommendation most of the time.

## Known setup limitations

- Requires Python 3.11+ and outbound network access to `api.groq.com` for a real (non-dry-run) run.
- Groq's free tier enforces per-minute and per-day request caps; `.env`'s `LLM_RPM_LIMIT` and
  `LLM_DAILY_SAFETY_CAP` are conservative defaults meant to stay under them.
- Each case folder must contain exactly the four files named above; the CLI raises a clear error
  naming any that are missing rather than failing silently.

## Approximate runtime and cost

One case: a single LLM call, typically 2-5 seconds, $0.00 (Groq's free tier).

## Relationship to the full proposal

The written proposal (problem definition, motivation and scope, evaluation plan, and limitations
and next steps) is submitted separately as the CSE598 capstone proposal document. This repository
is the "Runnable Baseline" and "Test Case and Baseline Output" evidence referenced from that
document.
