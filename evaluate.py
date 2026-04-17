"""
TEAM 4 — Evaluation Pipeline
==============================
Main entry point. Run this script to evaluate a batch of generated data
from any other team before it enters the final training corpus.

Usage:
    python evaluate.py --input data/sample_input.jsonl --output data/results/

What it does:
    1. Math-Verify     — checks math answers against ground truth
    2. Code Evaluation — runs code against unit tests, records pass@k
    3. Shepherd        — critiques <think> reasoning traces for logic errors
    4. Safety Check    — scans code for dangerous patterns

Outputs:
    accepted_data.jsonl      — clean verified entries ready for training
    rejected_data.jsonl      — discarded entries with rejection reasons
    evaluation_report.txt    — full summary stats
    eval_log_<timestamp>.jsonl — complete audit trail
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# ── Add project root to path so evaluators can find tools/ ───────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from evaluators.math_verifier  import MathVerifier
from evaluators.code_evaluator import CodeEvaluator
from evaluators.shepherd_critic import ShepherdCritic
from evaluators.safety_checker  import SafetyChecker
from utils.logger   import EvalLogger
from utils.reporter import generate_report


def load_data(input_path: str) -> list[dict]:
    """Load entries from a JSONL file."""
    if not os.path.exists(input_path):
        print(f"[ERROR] Input file not found: {input_path}")
        sys.exit(1)

    data = []
    with open(input_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[WARN] Skipping malformed JSON on line {i}: {e}")

    print(f"[INFO] Loaded {len(data)} entries from {input_path}")
    return data


def evaluate_entry(
    entry: dict,
    math_verifier:  MathVerifier,
    code_evaluator: CodeEvaluator,
    shepherd:       ShepherdCritic,
    safety_checker: SafetyChecker,
) -> dict:
    """
    Run all 4 evaluation checks on a single data entry.
    Returns the entry annotated with evaluation results.

    Which checks run depends on the domain field:
      math   → Math-Verify + Shepherd
      code   → Code Evaluation + Safety Check + Shepherd
      hybrid → All 4 checks
    """
    domain       = entry.get("domain", "unknown").lower()
    think_trace  = entry.get("think", "")
    solution     = entry.get("solution", "")
    ground_truth = entry.get("ground_truth", "")
    prompt       = entry.get("prompt", entry.get("Question", ""))
    unit_tests   = entry.get("unit_tests", [])

    result = {
        **entry,
        "eval_math_pass":        None,
        "eval_code_pass":        None,
        "eval_code_metrics":     None,
        "eval_safety_pass":      None,
        "eval_shepherd_pass":    None,
        "eval_rqs":              None,
        "eval_rejection_reason": [],
        "eval_final_verdict":    "PENDING",
    }

    # ── 1. MATH VERIFICATION ──────────────────────────────────────────
    if domain in ("math", "hybrid"):
        if ground_truth:
            passed, detail = math_verifier.verify(solution, ground_truth)
            result["eval_math_pass"] = passed
            if not passed:
                result["eval_rejection_reason"].append(
                    f"Math-Verify FAIL: {detail}"
                )
        else:
            # No ground truth supplied — skip math check
            result["eval_math_pass"] = None

    # ── 2. CODE EVALUATION (LiveCodeBench metrics) ────────────────────
    if domain in ("code", "hybrid"):
        input_output = entry.get("input_output", {})
        passed, metrics, detail = code_evaluator.evaluate(solution, unit_tests, input_output)
        result["eval_code_pass"]    = passed
        # Flatten metrics so reporter can read pass@k directly
        # Store full nested metrics and also lcb metrics at top level
        result["eval_code_metrics"]      = metrics.get("lcb") if isinstance(metrics, dict) else metrics
        result["eval_code_metrics_apps"] = metrics.get("apps") if isinstance(metrics, dict) else None
        result["eval_code_metrics_full"] = metrics
        if not passed:
            result["eval_rejection_reason"].append(
                f"Code-Eval FAIL: {detail}"
            )

    # ── 3. CODE SAFETY (Safety-Bench patterns) ────────────────────────
    if domain in ("code", "hybrid"):
        safe, violations = safety_checker.check(solution)
        result["eval_safety_pass"] = safe
        if not safe:
            result["eval_rejection_reason"].append(
                f"Safety FAIL: {'; '.join(violations[:3])}"
            )

    # ── 4. SHEPHERD REASONING CRITIQUE ────────────────────────────────
    # Runs on ALL domains — reasoning quality matters everywhere
    if think_trace and think_trace.strip():
        critique_pass, rqs, critique_detail = shepherd.critique(
            prompt, think_trace, solution
        )
        result["eval_shepherd_pass"] = critique_pass
        result["eval_rqs"]           = rqs
        if not critique_pass:
            result["eval_rejection_reason"].append(
                f"Shepherd FAIL (RQS={rqs:.2f}): {critique_detail}"
            )
    else:
        # No think trace present — flag it but don't hard-fail
        result["eval_shepherd_pass"] = None
        result["eval_rejection_reason"].append(
            "WARNING: No <think> trace found in this entry"
        )

    # ── FINAL VERDICT ─────────────────────────────────────────────────
    # PASS only if no hard failures (warnings don't count as failures)
    hard_failures = [
        r for r in result["eval_rejection_reason"]
        if not r.startswith("WARNING")
    ]
    result["eval_final_verdict"] = "PASS" if len(hard_failures) == 0 else "FAIL"

    return result


def run_pipeline(input_path: str, output_dir: str):
    """Main pipeline runner."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print("\n" + "="*60)
    print("  TEAM 4 — EVALUATION PIPELINE STARTING")
    print(f"  Input  : {input_path}")
    print(f"  Output : {output_dir}")
    print("="*60 + "\n")

    # ── Initialise all evaluators ─────────────────────────────────────
    print("[INIT] Loading all evaluators...")
    math_verifier  = MathVerifier()
    code_evaluator = CodeEvaluator()
    shepherd       = ShepherdCritic()
    safety_checker = SafetyChecker()
    logger         = EvalLogger(output_dir)
    print("[INIT] All evaluators ready.\n")

    data     = load_data(input_path)
    accepted = []
    rejected = []

    for i, entry in enumerate(data):
        entry_id = entry.get("id", i)
        domain   = entry.get("domain", "unknown")
        print(f"[{i+1:>4}/{len(data)}] id={entry_id}  domain={domain}")

        try:
            result = evaluate_entry(
                entry,
                math_verifier,
                code_evaluator,
                shepherd,
                safety_checker,
            )
        except Exception as e:
            print(f"         [ERROR] Pipeline crashed on this entry: {e}")
            result = {
                **entry,
                "eval_final_verdict":    "FAIL",
                "eval_rejection_reason": [f"Pipeline error: {str(e)}"],
            }

        verdict = result["eval_final_verdict"]
        reasons = result.get("eval_rejection_reason", [])
        rqs     = result.get("eval_rqs")

        if verdict == "PASS":
            print(f"         ✓ PASS  RQS={rqs}")
            accepted.append(result)
        else:
            print(f"         ✗ FAIL  reasons={reasons[:2]}")
            rejected.append(result)

        logger.log(result)

    logger.close()

    # ── Write accepted_data.jsonl ─────────────────────────────────────
    accepted_path = os.path.join(output_dir, "accepted_data.jsonl")
    with open(accepted_path, "w", encoding="utf-8") as f:
        for entry in accepted:
            f.write(json.dumps(entry) + "\n")

    # ── Write rejected_data.jsonl ─────────────────────────────────────
    rejected_path = os.path.join(output_dir, "rejected_data.jsonl")
    with open(rejected_path, "w", encoding="utf-8") as f:
        for entry in rejected:
            f.write(json.dumps(entry) + "\n")

    print(f"\n{'='*60}")
    print(f"  DONE")
    print(f"  Accepted : {len(accepted)}")
    print(f"  Rejected : {len(rejected)}")
    print(f"  accepted_data.jsonl → {accepted_path}")
    print(f"  rejected_data.jsonl → {rejected_path}")
    print(f"{'='*60}\n")

    # ── Generate report ───────────────────────────────────────────────
    report_path = generate_report(accepted, rejected, output_dir)
    print(f"  evaluation_report.txt → {report_path}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Team 4 — Synthetic Data Evaluation Pipeline"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input .jsonl file from any team"
    )
    parser.add_argument(
        "--output",
        default="data/results/",
        help="Output directory (default: data/results/)"
    )
    args = parser.parse_args()
    run_pipeline(args.input, args.output)
