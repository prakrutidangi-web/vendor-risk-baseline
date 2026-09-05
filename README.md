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

## Setup

```bash
git clone <this-repo-url>
cd vendor-risk-baseline
python3 -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and set `GROQ_API_KEY` to a free key from https://console.groq.com/keys (no credit
card required). Everything else in `.env` already has a safe default.

## Run it

```bash
python run_baseline.py --input examples/case_01_northwind_analytics
```

This prints the model's JSON response to stdout and also writes it to
`output/case_01_northwind_analytics_output.json`.

To try it with no API key at all (offline, canned response, useful for a quick sanity check):

```bash
DRY_RUN=true python run_baseline.py --input examples/case_01_northwind_analytics
```

See `examples/readme.md` for what the example input and output actually contain.

## Known setup limitations

- Requires Python 3.11+ and outbound network access to `api.groq.com` for a real (non-dry-run) run.
- Groq's free tier enforces per-minute and per-day request caps; `.env`'s `LLM_RPM_LIMIT` and
  `LLM_DAILY_SAFETY_CAP` are conservative defaults meant to stay under them.
- Each case folder must contain exactly the four files named in `examples/readme.md`; the CLI
  raises a clear error naming any that are missing rather than failing silently.

## Versions

Tested on Python 3.11. Pinned dependencies are in `requirements.txt`: `openai==3.6.0`,
`python-dotenv==1.0.1`, `tenacity==9.1.4`.

## Approximate runtime and cost

One case: a single LLM call, typically 2-5 seconds, $0.00 (Groq's free tier).

## Relationship to the full proposal

The written proposal (problem definition, motivation and scope, evaluation plan, and limitations
and next steps) is submitted separately as the CSE598 capstone proposal document. This repository
is the "Runnable Baseline" and "Test Case and Baseline Output" evidence referenced from that
document.
