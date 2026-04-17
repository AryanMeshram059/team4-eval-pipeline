"""
CodeParrot APPS Metric — evaluators/apps_evaluator.py
======================================================
Implements the APPS evaluation metric as described in:
https://huggingface.co/spaces/codeparrot/apps_metric

The original APPS metric uses pyext which is broken on Python 3.13.
We implement the core logic directly using the source from:
/home/iitgn_pt_data/.cache/huggingface/modules/evaluate_modules/
  metrics/codeparrot--apps_metric/.../utils.py

Key functions extracted and adapted:
  - estimate_pass_at_k  — exact same formula as APPS metric
  - get_results         — exact same logic as APPS metric
  - check_correctness   — reimplemented without pyext dependency
  - compute_metrics     — main entry point

Result codes (same as original APPS):
  -2 = compile error
  -1 = runtime error
  False = failed test case
  True  = passed test case
"""

import sys
import os
import json
import itertools
import tempfile
import subprocess
import multiprocessing
import numpy as np
from typing import Dict


TIMEOUT = 10   # seconds per test case, same as original APPS metric


# ── Core test runner (replaces pyext-dependent testing_util.run_test) ─

def _run_single_test(code: str, input_data: str, expected_output: str, timeout: int) -> bool:
    """
    Run generated code against a single input/output test case.
    Returns True if output matches expected, False otherwise.
    Uses subprocess for isolation (same approach as APPS internally).
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        actual = result.stdout.strip()
        expected = expected_output.strip()
        return actual == expected

    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False
    finally:
        os.unlink(tmp_path)


def _check_syntax(code: str) -> bool:
    """Check if code compiles without syntax errors."""
    try:
        compile(code, "<string>", "exec")
        return True
    except SyntaxError:
        return False


def check_correctness(code: str, input_output: dict, timeout: int = TIMEOUT) -> list:
    """
    Run code against all test cases from input_output dict.
    Returns list of results per test case:
      -2 = compile error
      -1 = runtime error  
      True/False = test passed/failed

    Mirrors the result format of the original APPS testing_util.run_test.
    """
    # Check syntax first
    if not _check_syntax(code):
        inputs = input_output.get("inputs", [])
        return [-2 for _ in inputs]

    inputs  = input_output.get("inputs", [])
    outputs = input_output.get("outputs", [])

    if not inputs:
        return [-1]

    results = []
    for inp, expected in zip(inputs, outputs):
        try:
            passed = _run_single_test(
                code,
                str(inp),
                str(expected),
                timeout=timeout,
            )
            results.append(True if passed else False)
        except Exception:
            results.append(-1)

    return results


# ── APPS metric functions (exact port from utils.py) ─────────────────

def estimate_pass_at_k(
    num_samples, num_correct, k: int
) -> np.ndarray:
    """
    Estimates pass@k of each problem and returns them in an array.
    Exact implementation from codeparrot/apps_metric utils.py.
    """
    def estimator(n: int, c: int, k: int) -> float:
        """Calculates 1 - comb(n - c, k) / comb(n, k)."""
        if n - c < k:
            return 1.0
        return 1.0 - np.prod(1.0 - k / np.arange(n - c + 1, n + 1))

    if isinstance(num_samples, int):
        num_samples_it = itertools.repeat(num_samples, len(num_correct))
    else:
        assert len(num_samples) == len(num_correct)
        num_samples_it = iter(num_samples)

    return np.array(
        [estimator(int(n), int(c), k) for n, c in zip(num_samples_it, num_correct)]
    )


def get_results(
    results: Dict[int, list],
    count_errors: bool = True,
    k_list: list = [1, 3, 5],
) -> dict:
    """
    Given results evaluated against test cases, compute APPS metrics.
    Exact logic from codeparrot/apps_metric utils.py get_results().

    For single generation per problem: avg_accuracy + strict_accuracy
    For multiple generations per problem: pass@k
    """
    metrics = {
        "avg_accuracy":   None,
        "strict_accuracy": None,
        "pass_at_k":      None,
    }

    if not results:
        return metrics

    if len(results[0]) == 1:
        # Single generation — compute avg_accuracy and strict_accuracy
        res          = []
        per_prob_res = []
        all_correct  = []

        for index in results:
            problem_results = np.asarray(results[index])
            res.extend(problem_results)
            per_prob_res.append(np.mean(problem_results > 0))
            all_correct.append(np.all(problem_results > 0))

        compile_errors  = len([e for e in res if -2 in (e if hasattr(e, '__iter__') else [e])])
        runtime_errors  = len([e for e in res if -1 in (e if hasattr(e, '__iter__') else [e])])
        total_testcases = len(res)

        metrics["avg_accuracy"]    = float(np.mean(per_prob_res))
        metrics["strict_accuracy"] = float(np.mean(all_correct))

    else:
        # Multiple generations — compute pass@k
        total   = []
        correct = []

        for index in results:
            all_correct = []
            for generation in results[index]:
                gen = np.array(generation)
                all_correct.append(bool(np.all(gen > 0)))
            total.append(len(all_correct))
            correct.append(sum(all_correct))

        total   = np.array(total)
        correct = np.array(correct)

        pass_at_k = {
            f"pass@{k}": float(estimate_pass_at_k(total, correct, k).mean())
            for k in k_list
            if (total >= k).all()
        }
        metrics["pass_at_k"] = pass_at_k

    return metrics


# ── Public evaluator class ────────────────────────────────────────────

class APPSEvaluator:
    """
    Evaluates generated code solutions using the APPS metric.

    Implements the CodeParrot APPS Metric without the pyext dependency,
    using the same result codes and pass@k formula.

    Usage:
        evaluator = APPSEvaluator()
        metrics = evaluator.evaluate(
            code="def solve(): ...",
            input_output={"inputs": ["1 2", "3 4"], "outputs": ["3", "7"]},
            k_list=[1, 3, 5]
        )

    Result codes (same as original APPS):
        -2    = compile error
        -1    = runtime error
        False = failed test case
        True  = passed test case
    """

    def __init__(self, timeout: int = TIMEOUT):
        self.timeout = timeout
        print("[APPSEvaluator] Loaded — CodeParrot APPS metric (pyext-free implementation)")

    def evaluate(
        self,
        code: str,
        input_output: dict,
        k_list: list = [1, 3, 5],
    ) -> dict:
        """
        Evaluate a single code solution against test cases.

        Args:
            code:         The generated code string
            input_output: Dict with 'inputs' and 'outputs' lists
            k_list:       List of k values for pass@k computation

        Returns:
            dict with keys:
              passed       (bool)   — overall pass/fail
              avg_accuracy (float)  — fraction of test cases passed
              strict_accuracy (float) — 1.0 only if ALL tests pass
              pass_at_k    (dict)   — pass@k metrics if k_list provided
              test_results (list)   — per-test result codes
              n_passed     (int)    — number of tests passed
              n_total      (int)    — total number of tests
        """
        if not input_output or not input_output.get("inputs"):
            # No test cases — fall back to syntax check only
            syntax_ok = _check_syntax(code)
            return {
                "passed":          syntax_ok,
                "avg_accuracy":    1.0 if syntax_ok else 0.0,
                "strict_accuracy": 1.0 if syntax_ok else 0.0,
                "pass_at_k":       None,
                "test_results":    [],
                "n_passed":        0,
                "n_total":         0,
                "source":          "APPS (syntax only)",
            }

        # Run against all test cases
        test_results = check_correctness(code, input_output, timeout=self.timeout)

        # Build results dict in APPS format: {problem_index: [per_test_results]}
        apps_results = {0: [test_results]}

        # Compute APPS metrics
        metrics = get_results(apps_results, count_errors=True, k_list=k_list)

        n_passed = sum(1 for r in test_results if r is True or r == True)
        n_total  = len(test_results)

        return {
            "passed":           bool(metrics.get("strict_accuracy", 0) == 1.0),
            "avg_accuracy":     metrics.get("avg_accuracy"),
            "strict_accuracy":  metrics.get("strict_accuracy"),
            "pass_at_k":        metrics.get("pass_at_k"),
            "test_results":     test_results,
            "n_passed":         n_passed,
            "n_total":          n_total,
            "source":           "APPS metric (codeparrot)",
        }
