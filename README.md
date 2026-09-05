# Vendor Risk Diligence Agent — Capstone Baseline

A procurement lead or vendor-risk manager approving a new SaaS vendor has to read a security
questionnaire, a draft contract, a financial summary, and reference-call notes, usually under a
deadline, usually for more than one vendor at a time. No single document tells the whole story: a
vendor can sound strong on a reference call while its own security questionnaire admits there's no
documented incident response plan; a contract can promise weaker breach-notification terms than
the sales team verbally claims; a pitch deck can say "record growth" the same quarter revenue
actually declined. Each document can read as fine in isolation while the real risk is hiding in the
gap *between* documents, and reviewers rarely have time to cross-check every claim in every source
against every other source, for every vendor.

**This repository is the minimal, runnable starting point for that problem**, submitted as the
"Runnable Baseline" evidence for a CSE 598 (Agentic AI) capstone proposal by Prakruti Dangi. It is
deliberately simple on purpose — see "What this baseline is, and isn't" below — so that the
structured, multi-agent system planned for later this semester has a fair, measurable "before" to
improve on.

## What this baseline actually does

One Python process, one LLM call: it loads all four of a vendor's documents as plain text,
concatenates them into a single fixed prompt (`baseline/prompts.py`) that asks the model for a
structured JSON risk brief, sends that one request to Groq, parses the JSON response, and returns
it. No decomposition into per-document extraction, no dedicated step for checking one document
against another, no mechanical check that the memo's claims are actually backed by the source text.
That's an intentional constraint, not an oversight: it's the cheapest fair comparison point
available, using the same model and the same four input documents the improved system will use
later, so any future improvement can be credited to *added structure*, not to a different model or
extra information the baseline didn't have.

```
financial_summary.md  ─┐
security_questionnaire.md ─┤
contract_draft.md      ─┼──►  one prompt  ──►  one Groq call  ──►  JSON risk brief
reference_notes.md    ─┘
```

## What this baseline is, and isn't

This is **not** the full system this project is aiming for — it's the "before" measurement the
proposal's evaluation plan (Section 6) needs. The planned system, described in the proposal's
Section 7 and sketched below, decomposes the same problem into cooperating agents and deterministic
tools:

```
START ─▶ extract_financial   ─┐
     ─▶ extract_security      ├─▶ cross_source_verifier ─▶ risk_synthesizer ─▶ memo_writer ─▶ citation_linter ─▶ human_checkpoint ─▶ END
     ─▶ extract_contract     ─┤
     ─▶ extract_reference   ─┘
```

Four extraction agents turn each document into structured, cited facts in parallel; a dedicated
cross-source verifier is given all four extractions together and looks specifically for
contradictions between them (the thing a single prompt tends to miss); deterministic, non-LLM tools
score risk categories with a fixed, reproducible formula and diff contract terms against a standard
policy instead of relying on the model's sense of what's "normal"; a citation linter mechanically
checks that every claim in the final memo traces back to real source text; and a human checkpoint
is the last node in the graph — the system never approves, rejects, or notifies a vendor on its
own.

**This isn't just a plan.** A working prototype of exactly this architecture already exists and has
been measured: I built and evaluated it independently as a personal project for the micro1 Frontier
Engineering Challenge hackathon (August 2026), before this course, and it is disclosed as such in
the proposal document (Section 7). Across ten synthetic evaluation cases with known planted issues,
that prototype cut false positives from 42 (single-prompt baseline) to 1, moving mean precision
from 0.19 to 0.95, while matching or exceeding the baseline's recall (full numbers and methodology:
`eval/results/results.json` in that repository). The working code, its own much more detailed
README, and its full evaluation harness and change log are public at
**https://github.com/prakrutidangi-web/vendor-risk-agent**.

The reason *this* repository still only contains the minimal single-call baseline, rather than that
already-working pipeline, is the assignment this repository was built for: the capstone proposal
stage explicitly asks for a minimal baseline as the comparison point a semester's worth of planned
work will be measured against, not the finished system itself. The multi-agent version is real,
it's measured, and it's linked above; it's just scoped as this semester's planned work in the
proposal rather than re-submitted here as if it were newly built for this course.

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
card required). Everything else already has a safe default:

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

## Input and output locations, and the test case

**Input:** `examples/case_01_northwind_analytics/` — four plain-text documents describing one
fictional SaaS vendor being evaluated for a procurement decision:

- `financial_summary.md`: quarterly revenue, customer concentration, runway
- `security_questionnaire.md`: encryption, MFA, incident response, breach notification, SOC 2
- `contract_draft.md`: liability cap, indemnification, breach notification SLA, termination terms
- `reference_notes.md`: a customer reference call

This case is deliberately adversarial: on the surface the vendor looks strong (revenue growing,
SOC 2 Type II, a positive reference call), but its own security questionnaire admits there is no
documented incident response plan. A careful human reviewer should flag that gap as the primary
concern. Whether the baseline notices it at all — and what else it flags alongside it — is exactly
what this test case checks, and is the comparison point the improved system will be measured
against later this semester.

**Output:** printed to stdout and written to `output/case_01_northwind_analytics_output.json`.
`examples/expected_output/case_01_northwind_analytics_baseline_output.json` is the actual output
this baseline produced for this case on a real run against Groq — not a hypothetical or
hand-written example — and
`examples/expected_output/case_01_northwind_analytics_baseline_output_screenshot.png` is a
screenshot of that same terminal run, showing the baseline executing successfully end to end. On
that real run, the baseline caught the intended issue (`no_formal_incident_response_plan`) and
recommended `approve_with_conditions`, but it also flagged the contract's standard 3x-fees
liability cap (`liability_cap_limit`) as a concern even though that term is typical and not
actually problematic — a well-written but not load-bearing false alarm, and exactly the kind of
noise the planned cross-source verifier and deterministic policy-diff tool are meant to reduce.
Running the command again will not reproduce that exact text byte-for-byte, since the model is
called at a low but nonzero temperature, but it should land on materially the same finding most of
the time.

## Known limitations of this baseline

- **No cross-document check.** It reads all four documents in one pass and asks the model to reason
  about all of them at once; it never explicitly extracts structured facts from one document and
  checks them against another the way the planned `cross_source_verifier` will.
- **No check against a defined standard.** It has no deterministic policy to compare a contract
  term against, so it relies entirely on the model's own sense of what's "normal" — which is why it
  raised the standard liability cap as a concern above.
- **No citation enforcement.** Nothing verifies that a claim in the memo actually traces back to
  real text in one of the four source documents; a fabricated-sounding but plausible claim would
  currently pass through unchecked.
- **Fixed four-document shape.** The prompt and the file-existence check both assume exactly one
  financial summary, one security questionnaire, one contract, and one reference-call writeup, in
  the four fixed filenames listed above.

## About the free-tier API

Groq's API is OpenAI-protocol-compatible, reached here through the official `openai` Python SDK
pointed at Groq's base URL. The free tier enforces real per-minute and per-day request caps rather
than a spend-based limit, so `baseline/llm.py` (adapted from the same client used in the hackathon
prototype above) handles the ways a free third-party API actually fails in practice, not just the
happy path:

- Rate-limits calls locally (`LLM_RPM_LIMIT`) so the client doesn't trip a 429 in the first place.
- Retries transient errors (429 rate limit; 500/502/503/504 server errors; flaky network) with
  exponential backoff (`LLM_MAX_RETRIES`).
- Falls back automatically to the next model in `GROQ_FALLBACK_MODELS` if the primary model 404s
  (renamed, retired, or not enabled for a given key).
- Enforces a local daily-call safety cap (`LLM_DAILY_SAFETY_CAP`), set a bit below Groq's own daily
  limit, so a runaway loop can't silently burn a whole day's quota.
- `DRY_RUN=true` runs the whole CLI with zero network calls, using a canned fixture response, so
  the plumbing can be graded or debugged without an API key at all.

If a real run does hit a wall: lower `LLM_RPM_LIMIT`, check current limits at
https://console.groq.com/settings/limits, or wait for the free tier's daily reset.

## Repository layout

```
run_baseline.py                    CLI entry point
baseline/baseline.py               the single LLM call
baseline/prompts.py                the exact prompt template
baseline/llm.py                    Groq client: retries, rate limiting, fallback, dry-run mode
baseline/dry_run_fixtures.py       canned offline response for DRY_RUN=true
examples/case_01_northwind_analytics/   the test case input (four documents)
examples/expected_output/          the real captured output and a terminal screenshot of it
requirements.txt, .env.example     dependencies and configuration template
```

## What existed before this course vs. what was built for it

The problem, the four-document framing, and the multi-agent architecture referenced above all
originate from a personal hackathon project completed before this course (disclosed in the
proposal, Section 7, and linked above). Everything in *this specific repository* — the single-call
baseline, its prompt, its CLI, and its test case packaging — was newly implemented for this capstone
proposal as the semester's comparison point; no code from the hackathon repository's multi-agent
pipeline is copied into this one.

## Relationship to the full written proposal

The written proposal (problem definition, motivation and scope, evaluation plan, and limitations
and next steps) is submitted separately as the CSE598 capstone proposal document. This repository
is the "Runnable Baseline" and "Test Case and Baseline Output" evidence referenced from that
document.
