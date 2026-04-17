"""
Evaluation Logger — utils/logger.py
=====================================
Writes a running JSONL audit log of every evaluated entry.
Every decision, pass or fail, is recorded here with full context
so the team has a complete audit trail.
"""

import json
import os
from datetime import datetime


class EvalLogger:
    """
    Logs every evaluation decision to a JSONL audit file.

    Usage:
        logger = EvalLogger("data/results/")
        logger.log(result_dict)
        logger.close()
    """

    def __init__(self, output_dir: str):
        os.makedirs(output_dir, exist_ok=True)
        timestamp     = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = os.path.join(output_dir, f"eval_log_{timestamp}.jsonl")
        self._file    = open(self.log_path, "w", encoding="utf-8")
        self.n_logged = 0
        print(f"[EvalLogger] Audit log → {self.log_path}")

    def log(self, result: dict):
        """Write a single evaluated entry to the audit log."""
        record = {
            "timestamp":        datetime.now().isoformat(),
            "id":               result.get("id", self.n_logged),
            "domain":           result.get("domain", "unknown"),
            "difficulty":       result.get("difficulty", None),
            "source":           result.get("source", None),
            "verdict":          result.get("eval_final_verdict"),
            "math_pass":        result.get("eval_math_pass"),
            "code_pass":        result.get("eval_code_pass"),
            "code_metrics":     result.get("eval_code_metrics"),
            "safety_pass":      result.get("eval_safety_pass"),
            "shepherd_pass":    result.get("eval_shepherd_pass"),
            "rqs":              result.get("eval_rqs"),
            "rejection_reasons": result.get("eval_rejection_reason", []),
        }
        self._file.write(json.dumps(record) + "\n")
        self._file.flush()
        self.n_logged += 1

    def close(self):
        self._file.close()

    def __del__(self):
        try:
            self._file.close()
        except Exception:
            pass
