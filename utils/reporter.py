"""
Report Generator — utils/reporter.py
======================================
Generates the evaluation report after each batch run.
Covers all deliverables required by Team 4 documentation:
  - Overall pass/fail counts
  - Pass rates by domain and difficulty level (0-4)
  - Math-Verify accuracy
  - Code pass@k metrics (from LiveCodeBench)
  - Shepherd RQS distribution
  - Top rejection reasons mapped to evaluation component
  - Code Safety violations by type
"""

import os
import json
from collections import defaultdict, Counter
from datetime import datetime


def _safe_mean(values: list) -> float:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else 0.0


def _safe_pct(n: int, total: int) -> str:
    if total == 0:
        return "N/A"
    return f"{100 * n / total:.1f}%"


def generate_report(
    accepted: list[dict], rejected: list[dict], output_dir: str
) -> str:
    """
    Writes a plain-text evaluation report to output_dir/evaluation_report.txt.
    Returns the path to the report file.
    """
    all_entries = accepted + rejected
    total       = len(all_entries)
    n_accepted  = len(accepted)
    n_rejected  = len(rejected)

    # ── Pass rates by domain ──────────────────────────────────────────
    domain_stats = defaultdict(lambda: {"pass": 0, "fail": 0})
    for e in all_entries:
        d = e.get("domain", "unknown")
        v = e.get("eval_final_verdict", "FAIL")
        domain_stats[d]["pass" if v == "PASS" else "fail"] += 1

    # ── Pass rates by difficulty level (0-4) ─────────────────────────
    diff_stats = defaultdict(lambda: {"pass": 0, "fail": 0})
    for e in all_entries:
        d = e.get("difficulty", "unknown")
        v = e.get("eval_final_verdict", "FAIL")
        diff_stats[d]["pass" if v == "PASS" else "fail"] += 1

    # ── Math-Verify accuracy ──────────────────────────────────────────
    math_results = [
        e.get("eval_math_pass")
        for e in all_entries
        if e.get("eval_math_pass") is not None
    ]
    math_pass_rate = (
        sum(math_results) / len(math_results) if math_results else None
    )

    # ── Code pass@k (from LiveCodeBench metrics) ──────────────────────
    code_entries = [
        e for e in all_entries
        if e.get("eval_code_metrics") and isinstance(e.get("eval_code_metrics"), dict)
    ]
    pass_at_1 = _safe_mean([e["eval_code_metrics"].get("pass@1") for e in code_entries])
    pass_at_3 = _safe_mean([e["eval_code_metrics"].get("pass@3") for e in code_entries])
    pass_at_5 = _safe_mean([e["eval_code_metrics"].get("pass@5") for e in code_entries])
    lcb_source = code_entries[0]["eval_code_metrics"].get("source", "manual") if code_entries else "N/A"

    # ── Shepherd RQS distribution ─────────────────────────────────────
    rqs_values = [
        e.get("eval_rqs")
        for e in all_entries
        if e.get("eval_rqs") is not None
    ]
    rqs_mean = _safe_mean(rqs_values)
    rqs_bins = Counter()
    for v in rqs_values:
        low    = int(v * 10) * 10
        high   = low + 10
        bucket = f"{low:3d}-{high:3d}%"
        rqs_bins[bucket] += 1

    # ── Rejection reasons ─────────────────────────────────────────────
    all_reasons = []
    for e in rejected:
        all_reasons.extend(e.get("eval_rejection_reason", []))

    reason_categories = Counter()
    for r in all_reasons:
        if "Math-Verify" in r:
            reason_categories["Math answer mismatch (Math-Verify)"] += 1
        elif "Code-Eval" in r:
            reason_categories["Code test failures (LiveCodeBench)"] += 1
        elif "Safety" in r:
            reason_categories["Code safety violation (Safety-Bench)"] += 1
        elif "Shepherd" in r:
            reason_categories["Reasoning trace rejected (Shepherd)"] += 1
        elif "Pipeline" in r:
            reason_categories["Pipeline error"] += 1
        else:
            reason_categories["Other"] += 1

    # ── Safety violations by type ─────────────────────────────────────
    safety_violations = Counter()
    for e in all_entries:
        for reason in e.get("eval_rejection_reason", []):
            if "Safety" in reason:
                # Extract benchmark type from violation string
                match = __import__("re").search(r"benchmark: '([^']+)'", reason)
                if match:
                    safety_violations[match.group(1)] += 1
                else:
                    safety_violations["Unknown"] += 1

    # ── Build report ──────────────────────────────────────────────────
    sep  = "=" * 62
    sep2 = "-" * 42
    lines = [
        sep,
        "  TEAM 4 — SYNTHETIC DATA EVALUATION REPORT",
        f"  Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  Tools     : Math-Verify | LiveCodeBench | Shepherd-7B | Safety-Bench",
        sep,
        "",
        "OVERALL RESULTS",
        sep2,
        f"  Total evaluated  : {total}",
        f"  Accepted (PASS)  : {n_accepted}  ({_safe_pct(n_accepted, total)})",
        f"  Rejected (FAIL)  : {n_rejected}  ({_safe_pct(n_rejected, total)})",
        "",
        "PASS RATE BY DOMAIN",
        sep2,
    ]

    for domain, counts in sorted(domain_stats.items()):
        p = counts["pass"]
        t = p + counts["fail"]
        lines.append(
            f"  {domain:<12}  {p:>4}/{t:<4}  ({_safe_pct(p, t)})"
        )

    lines += ["", "PASS RATE BY DIFFICULTY LEVEL (0=Minimal → 4=Expert)", sep2]
    for diff in sorted(diff_stats.keys(), key=lambda x: str(x)):
        p = diff_stats[diff]["pass"]
        t = p + diff_stats[diff]["fail"]
        lines.append(
            f"  Level {str(diff):<6}  {p:>4}/{t:<4}  ({_safe_pct(p, t)})"
        )

    lines += [
        "",
        "MATH-VERIFY (HuggingFace math-verify library)",
        sep2,
    ]
    if math_pass_rate is not None:
        lines.append(
            f"  Pass rate : {100*math_pass_rate:.1f}%  "
            f"({len(math_results)} math entries evaluated)"
        )
    else:
        lines.append("  No math entries evaluated.")

    lines += [
        "",
        f"CODE EVALUATION — pass@k  (source: {lcb_source})",
        sep2,
    ]
    if code_entries:
        lines += [
            f"  pass@1 : {100*pass_at_1:.1f}%",
            f"  pass@3 : {100*pass_at_3:.1f}%",
            f"  pass@5 : {100*pass_at_5:.1f}%",
            f"  ({len(code_entries)} code entries evaluated)",
        ]
    else:
        lines.append("  No code entries evaluated.")

    lines += [
        "",
        "SHEPHERD — REASONING QUALITY SCORE (RQS)  [0.0 = poor, 1.0 = perfect]",
        sep2,
    ]
    if rqs_values:
        lines.append(
            f"  Mean RQS : {rqs_mean:.3f}  ({len(rqs_values)} entries scored)"
        )
        lines.append("  Distribution:")
        for bucket, count in sorted(rqs_bins.items()):
            bar = "█" * min(count, 30)
            lines.append(f"    {bucket}  {bar} {count}")
    else:
        lines.append("  No RQS data available.")

    lines += ["", "TOP REJECTION REASONS", sep2]
    if reason_categories:
        for reason, count in reason_categories.most_common():
            lines.append(f"  {count:>4}x  {reason}")
    else:
        lines.append("  No rejections — all entries passed.")

    if safety_violations:
        lines += ["", "SAFETY VIOLATIONS BY BENCHMARK TYPE", sep2]
        for vtype, count in safety_violations.most_common():
            lines.append(f"  {count:>4}x  {vtype}")

    lines += ["", sep, ""]

    report_text = "\n".join(lines)

    # Write to file
    report_path = os.path.join(output_dir, "evaluation_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print("\n" + report_text)
    return report_path
