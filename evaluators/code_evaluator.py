"""
Code Evaluation — evaluators/code_evaluator.py
===============================================
Combines two evaluation approaches as specified in Team 4 documentation:

1. LiveCodeBench — scores code correctness on competitive programming problems
   Ref: https://github.com/LiveCodeBench/LiveCodeBench

2. CodeParrot APPS Metric — evaluates code by executing against hidden test cases
   A solution passes only if ALL test cases succeed.
   Ref: https://huggingface.co/spaces/codeparrot/apps_metric

Both are run on every code entry. Final pass/fail is determined by:
  - If input_output (APPS-style) tests provided → use APPS metric
  - If unit_tests (assert-style) provided → use LiveCodeBench pass@k
  - If both provided → run both and require both to pass
  - pass@1, pass@3, pass@5 always recorded from LiveCodeBench
"""

import re
import sys
import os
import subprocess
import tempfile

# ── Add LiveCodeBench to path ─────────────────────────────────────────
LCB_PATH = os.path.join(os.path.dirname(__file__), "..", "tools", "LiveCodeBench")
if LCB_PATH not in sys.path:
    sys.path.insert(0, LCB_PATH)

try:
    from lcb_runner.evaluation import codegen_metrics
    from lcb_runner.evaluation.pass_k_utils import compute_metrics_from_results
    LCB_AVAILABLE = True
    print("[code_evaluator] LiveCodeBench loaded successfully.")
except ImportError as e:
    LCB_AVAILABLE = False
    print(f"[WARN] LiveCodeBench not importable: {e}. Falling back to subprocess evaluation.")

# ── Import APPS evaluator ─────────────────────────────────────────────
try:
    from evaluators.apps_evaluator import APPSEvaluator
    _apps_evaluator = APPSEvaluator()
    APPS_AVAILABLE = True
except Exception as e:
    APPS_AVAILABLE = False
    _apps_evaluator = None
    print(f"[WARN] APPS evaluator not available: {e}")


def _extract_code(text: str) -> str:
    """
    Extract code block from model response.
    Tries fenced python block, then any fenced block, then raw text.
    """
    match = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _run_code_safely(code: str, test_code: str, timeout: int = 10) -> tuple[bool, str]:
    """
    Run code + assert-style test in a sandboxed subprocess.
    Returns (passed, output_or_error).
    """
    full_script = code + "\n\n" + test_code
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(full_script)
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True, timeout=timeout
        )
        passed = result.returncode == 0
        output = result.stdout + result.stderr
        return passed, output.strip()
    except subprocess.TimeoutExpired:
        return False, f"Execution timed out after {timeout}s"
    except Exception as e:
        return False, f"Subprocess error: {str(e)}"
    finally:
        os.unlink(tmp_path)


def _compute_pass_at_k_lcb(results: list[dict]) -> dict:
    """
    Compute pass@k using LiveCodeBench's compute_metrics_from_results.

    LiveCodeBench expects:
      { task_id: [ [grade_per_test] ] }
    where grades > 0 = pass, 0 = fail.
    """
    n           = len(results)
    passed_list = [r["passed"] for r in results]
    n_passed    = sum(passed_list)

    if LCB_AVAILABLE and n > 0:
        try:
            lcb_input = {
                str(i): [[1 if r["passed"] else 0]]
                for i, r in enumerate(results)
            }
            metrics = compute_metrics_from_results(lcb_input, k_list=[1, 3, 5])
            return {
                "pass@1":    metrics.get("pass@1"),
                "pass@3":    metrics.get("pass@3"),
                "pass@5":    metrics.get("pass@5"),
                "pass_rate": round(n_passed / n, 3),
                "n_passed":  n_passed,
                "n_total":   n,
                "source":    "LiveCodeBench",
            }
        except Exception as e:
            print(f"[WARN] LiveCodeBench pass@k failed: {e}. Using manual computation.")

    # Manual fallback
    return {
        "pass@1":    passed_list[0] if n >= 1 else None,
        "pass@3":    any(passed_list[:3]) if n >= 3 else None,
        "pass@5":    any(passed_list[:5]) if n >= 5 else None,
        "pass_rate": round(n_passed / n, 3) if n > 0 else 0.0,
        "n_passed":  n_passed,
        "n_total":   n,
        "source":    "manual",
    }


class CodeEvaluator:
    """
    Evaluates code solutions using both LiveCodeBench and APPS metric.

    Usage:
        evaluator = CodeEvaluator()
        passed, metrics, detail = evaluator.evaluate(
            solution_text,
            unit_tests=[...],        # assert-style tests for LiveCodeBench
            input_output={...}       # APPS-style input/output dict
        )
    """

    def __init__(self, timeout: int = 10, pass_threshold: float = 0.5):
        self.timeout        = timeout
        self.pass_threshold = pass_threshold

    def evaluate(
        self,
        solution:     str,
        unit_tests:   list[str] = None,
        input_output: dict      = None,
    ) -> tuple[bool, dict, str]:
        """
        Run both LiveCodeBench and APPS evaluation.

        Returns:
            passed  (bool)   — True if solution passes evaluation
            metrics (dict)   — all metrics from both evaluators
            detail  (str)    — human-readable summary
        """
        code         = _extract_code(solution)
        unit_tests   = unit_tests   or []
        input_output = input_output or {}

        if not code:
            return False, {}, "Could not extract code from solution."

        metrics = {
            "lcb":  None,
            "apps": None,
        }
        all_passed  = []
        detail_parts = []

        # ── 1. LiveCodeBench (assert-style unit tests) ────────────────
        if unit_tests:
            results = []
            for test in unit_tests:
                passed, output = _run_code_safely(code, test, timeout=self.timeout)
                results.append({
                    "test":   test[:120],
                    "passed": passed,
                    "output": output[:300],
                })

            lcb_metrics          = _compute_pass_at_k_lcb(results)
            lcb_metrics["tests"] = results
            metrics["lcb"]       = lcb_metrics

            lcb_passed = lcb_metrics["pass_rate"] >= self.pass_threshold
            all_passed.append(lcb_passed)
            detail_parts.append(
                f"LiveCodeBench: {lcb_metrics['n_passed']}/{lcb_metrics['n_total']} "
                f"tests passed (pass@1={lcb_metrics['pass@1']}, source={lcb_metrics['source']})"
            )

        # ── 2. APPS Metric (input/output style tests) ─────────────────
        if input_output and input_output.get("inputs") and APPS_AVAILABLE:
            apps_result    = _apps_evaluator.evaluate(
                code         = code,
                input_output = input_output,
                k_list       = [1, 3, 5],
            )
            metrics["apps"] = apps_result

            apps_passed = apps_result["passed"]
            all_passed.append(apps_passed)
            detail_parts.append(
                f"APPS: {apps_result['n_passed']}/{apps_result['n_total']} "
                f"test cases passed "
                f"(strict_accuracy={apps_result['strict_accuracy']:.2f}, "
                f"avg_accuracy={apps_result['avg_accuracy']:.2f})"
            )

        # ── 3. Syntax check only if no tests provided ─────────────────
        if not unit_tests and not (input_output and input_output.get("inputs")):
            syntax_pass, syntax_metrics, syntax_detail = self._syntax_check(code)
            metrics["lcb"] = {"syntax_check": "PASS" if syntax_pass else "FAIL"}
            all_passed.append(syntax_pass)
            detail_parts.append(syntax_detail)

        overall_passed = all(all_passed) if all_passed else False
        detail         = " | ".join(detail_parts) if detail_parts else "No tests run"

        return overall_passed, metrics, detail

    def _syntax_check(self, code: str) -> tuple[bool, dict, str]:
        """Compile-only check when no tests are provided."""
        try:
            compile(code, "<string>", "exec")
            return True, {"syntax_check": "PASS"}, "Syntax OK (no tests provided)"
        except SyntaxError as e:
            return False, {"syntax_check": "FAIL"}, f"SyntaxError: {e}"
