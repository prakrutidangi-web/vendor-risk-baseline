"""CLI entry point for the baseline.

Usage:
    python run_baseline.py --input examples/case_01_northwind_analytics
    DRY_RUN=true python run_baseline.py --input examples/case_01_northwind_analytics

Prints the model's JSON response (memo, identified_issues, recommendation)
to stdout, and also writes it to output/<case_id>_output.json.

Submission by Prakruti Dangi.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from baseline.baseline import run_baseline_case

OUT_DIR = Path(__file__).resolve().parent / "output"


def main():
    parser = argparse.ArgumentParser(description="Run the single-prompt vendor-risk baseline on one case.")
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to a folder containing financial_summary.md, security_questionnaire.md, "
        "contract_draft.md, and reference_notes.md (see examples/case_01_northwind_analytics).",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"No such folder: {args.input}")

    result = run_baseline_case(args.input)

    print(json.dumps(result, indent=2))

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / f"{result['case_id']}_output.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
