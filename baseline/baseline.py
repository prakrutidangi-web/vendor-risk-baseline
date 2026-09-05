"""The runnable baseline for this proposal: one direct prompt with all four
vendor documents dumped into context, no decomposition, no tools, no
verification step. This is the minimal starting point the capstone project
will be measured against in later phases.

Submission by Prakruti Dangi.
"""
from __future__ import annotations

from pathlib import Path

from baseline import dry_run_fixtures as fx
from baseline import prompts
from baseline.llm import LLMClient, get_client

REQUIRED_FILES = (
    "financial_summary.md",
    "security_questionnaire.md",
    "contract_draft.md",
    "reference_notes.md",
)


def run_baseline_case(case_dir: Path, client: LLMClient | None = None) -> dict:
    """Run the single-prompt baseline over one case folder.

    Args:
        case_dir: Path to a folder containing the four vendor documents
            (financial_summary.md, security_questionnaire.md,
            contract_draft.md, reference_notes.md).
        client: LLM client to use. Defaults to the shared singleton client.

    Returns:
        The model's JSON response (memo, identified_issues, recommendation)
        with ``case_id`` added.
    """
    client = client or get_client()
    case_dir = Path(case_dir)

    missing = [name for name in REQUIRED_FILES if not (case_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"{case_dir} is missing required file(s): {', '.join(missing)}. "
            f"A case folder needs all four: {', '.join(REQUIRED_FILES)}."
        )

    financial_text = (case_dir / "financial_summary.md").read_text()
    security_text = (case_dir / "security_questionnaire.md").read_text()
    contract_text = (case_dir / "contract_draft.md").read_text()
    reference_text = (case_dir / "reference_notes.md").read_text()

    prompt = prompts.BASELINE_PROMPT.format(
        financial_text=financial_text,
        security_text=security_text,
        contract_text=contract_text,
        reference_text=reference_text,
    )
    result = client.invoke_json(prompt, dry_run_response=fx.baseline_fixture(case_dir.name))
    result["case_id"] = case_dir.name
    return result
