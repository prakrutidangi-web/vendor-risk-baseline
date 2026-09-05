"""Canned, offline response returned when DRY_RUN=true, so anyone grading
this can prove the code runs end to end without a Groq API key.

Submission by Prakruti Dangi.
"""


def baseline_fixture(case_id: str) -> dict:
    """Canned response for ``run_baseline_case()`` in dry-run mode."""
    return {
        "memo": (
            f"# Vendor Risk Brief: {case_id}\n\n"
            "[DRY_RUN] This is a canned placeholder memo returned instead of "
            "a real model call. Set DRY_RUN=false and add a real GROQ_API_KEY "
            "in .env to see the model's actual output."
        ),
        "identified_issues": [],
        "recommendation": "approve",
    }
