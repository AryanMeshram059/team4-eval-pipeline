"""
Universal Schema Merger — merge_datasets.py
============================================
Team 4 responsibility (per Mar 17 suggestion):
"If some specific schema is to be followed for merging all the datasets
into a universal format then that is to be done by you."

This script:
  1. Takes accepted_data.jsonl files from all teams
  2. Normalises every entry to the universal SFT/RL schema
  3. Validates required fields are present
  4. Deduplicates by prompt hash
  5. Outputs a single merged dataset in both JSONL and parquet format

Universal SFT Schema (from Appendix A.2 of documentation):
  {
    "prompt":       str,
    "response":     "<think>...</think>\n[final answer]",
    "domain":       "math | code | hybrid | nl",
    "sub_domain":   str,
    "difficulty":   int (0-4),
    "source":       str (which team generated this),
    "verified_by":  list,
    "eval_rqs":     float (Shepherd RQS score from Team 4),
  }

Universal RL Schema (from Appendix A.1 of documentation):
  {
    "prompt":        str,
    "ground_truth":  str (stored as metadata, NOT in prompt),
    "domain":        str,
    "difficulty":    int,
    "reward_format": float (+1.0 if <think>+<answer> tags present),
    "reward_accuracy": float (+1.0 if answer matches ground truth),
    "source":        str,
  }

Usage:
    # Merge specific team files
    python merge_datasets.py \\
        --inputs team1/accepted_data.jsonl team2/accepted_data.jsonl \\
        --output merged/final_dataset \\
        --mode sft

    # Merge all accepted_data.jsonl found under a directory
    python merge_datasets.py \\
        --scan /projects/data/datasets/code_post_training_data/ \\
        --output merged/final_dataset \\
        --mode sft
"""

import argparse
import json
import os
import hashlib
import glob
from pathlib import Path
from datetime import datetime

try:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    PARQUET_AVAILABLE = True
except ImportError:
    PARQUET_AVAILABLE = False
    print("[WARN] pandas/pyarrow not available. Will output JSONL only.")


# ── Universal schema field definitions ───────────────────────────────

REQUIRED_FIELDS_SFT = ["prompt", "response", "domain"]
REQUIRED_FIELDS_RL  = ["prompt", "ground_truth", "domain"]

VALID_DOMAINS     = {"math", "code", "hybrid", "nl", "unknown"}
VALID_DIFFICULTIES = {0, 1, 2, 3, 4}


def _prompt_hash(prompt: str) -> str:
    """Generate a hash for deduplication based on the prompt."""
    return hashlib.md5(prompt.strip().lower().encode()).hexdigest()


def _build_response(entry: dict) -> str:
    """
    Build the unified response field from think + solution.
    Format: <think>...</think>\n[final answer]
    """
    think    = entry.get("think", "").strip()
    solution = entry.get("solution", entry.get("response", "")).strip()

    if think and solution:
        return f"<think>\n{think}\n</think>\n{solution}"
    elif solution:
        return solution
    elif think:
        return f"<think>\n{think}\n</think>"
    return ""


def _normalise_sft(entry: dict, source_file: str) -> dict | None:
    """
    Normalise any entry to the universal SFT schema.
    Returns None if entry cannot be normalised.
    """
    prompt = entry.get("prompt") or entry.get("Question") or entry.get("instruction", "")
    if not prompt:
        return None

    response = _build_response(entry)
    if not response:
        return None

    domain     = entry.get("domain", "unknown").lower()
    difficulty = entry.get("difficulty", -1)

    # Coerce difficulty to int in range 0-4
    try:
        difficulty = int(difficulty)
        if difficulty not in VALID_DIFFICULTIES:
            difficulty = -1
    except (TypeError, ValueError):
        difficulty = -1

    return {
        # ── Core SFT fields ───────────────────────────────────────────
        "prompt":       prompt.strip(),
        "response":     response,

        # ── Classification ────────────────────────────────────────────
        "domain":       domain if domain in VALID_DOMAINS else "unknown",
        "sub_domain":   entry.get("sub_domain", entry.get("task", "")),
        "difficulty":   difficulty,

        # ── Provenance ────────────────────────────────────────────────
        "source":       entry.get("source", os.path.basename(source_file)),
        "source_file":  source_file,
        "original_id":  str(entry.get("id", "")),
        "verified_by":  entry.get("verified_by", []),

        # ── Team 4 evaluation metadata ────────────────────────────────
        "eval_rqs":           entry.get("eval_rqs"),
        "eval_math_pass":     entry.get("eval_math_pass"),
        "eval_code_pass":     entry.get("eval_code_pass"),
        "eval_safety_pass":   entry.get("eval_safety_pass"),
        "eval_shepherd_pass": entry.get("eval_shepherd_pass"),

        # ── Optional extras ───────────────────────────────────────────
        "ground_truth": entry.get("ground_truth", ""),
        "language":     entry.get("language", ""),
        "tags":         entry.get("task", entry.get("tags", [])),
    }


def _normalise_rl(entry: dict, source_file: str) -> dict | None:
    """
    Normalise any entry to the universal RL schema.
    Returns None if entry has no ground truth (required for RL).
    """
    prompt       = entry.get("prompt") or entry.get("Question", "")
    ground_truth = entry.get("ground_truth", "")

    if not prompt:
        return None

    # For RL, ground truth is required for reward computation
    if not ground_truth:
        return None

    response   = _build_response(entry)
    think      = entry.get("think", "")
    solution   = entry.get("solution", "")

    # Reward Function 1 — Format: +1.0 if <think> and <answer> tags present
    has_think  = bool(think and think.strip())
    has_answer = bool(solution and solution.strip())
    reward_format = 1.0 if (has_think and has_answer) else 0.0

    # Reward Function 2 — Accuracy: stored as metadata from Team 4 eval
    reward_accuracy = 1.0 if entry.get("eval_math_pass") or entry.get("eval_code_pass") else 0.0

    return {
        "prompt":           prompt.strip(),
        "ground_truth":     ground_truth,
        "domain":           entry.get("domain", "unknown").lower(),
        "difficulty":       entry.get("difficulty", -1),
        "reward_format":    reward_format,
        "reward_accuracy":  reward_accuracy,
        "source":           entry.get("source", os.path.basename(source_file)),
        "original_id":      str(entry.get("id", "")),
        "eval_rqs":         entry.get("eval_rqs"),
    }


def load_jsonl(path: str) -> list[dict]:
    """Load all entries from a JSONL file."""
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[WARN] Skipping malformed line {i} in {path}: {e}")
    return entries


def scan_for_accepted(root_dir: str) -> list[str]:
    """Find all accepted_data.jsonl files under a directory."""
    pattern = os.path.join(root_dir, "**/accepted_data.jsonl")
    found   = glob.glob(pattern, recursive=True)
    print(f"[SCAN] Found {len(found)} accepted_data.jsonl files under {root_dir}")
    for f in found:
        print(f"       {f}")
    return found


def merge(
    input_files: list[str],
    output_path: str,
    mode: str = "sft",
) -> dict:
    """
    Main merge function.

    Args:
        input_files: list of paths to accepted_data.jsonl files
        output_path: output path prefix (without extension)
        mode:        "sft" or "rl"

    Returns:
        stats dict
    """
    Path(os.path.dirname(output_path) or ".").mkdir(parents=True, exist_ok=True)

    normalise_fn = _normalise_sft if mode == "sft" else _normalise_rl

    all_entries  = []
    seen_hashes  = set()
    stats = {
        "total_loaded":    0,
        "total_accepted":  0,
        "duplicates":      0,
        "schema_failures": 0,
        "by_source":       {},
        "by_domain":       {},
        "by_difficulty":   {},
    }

    for input_file in input_files:
        if not os.path.exists(input_file):
            print(f"[WARN] File not found, skipping: {input_file}")
            continue

        entries = load_jsonl(input_file)
        print(f"[LOAD] {len(entries):>5} entries from {input_file}")
        stats["total_loaded"] += len(entries)

        for entry in entries:
            normalised = normalise_fn(entry, input_file)

            if normalised is None:
                stats["schema_failures"] += 1
                continue

            # Deduplicate by prompt hash
            ph = _prompt_hash(normalised["prompt"])
            if ph in seen_hashes:
                stats["duplicates"] += 1
                continue
            seen_hashes.add(ph)

            all_entries.append(normalised)
            stats["total_accepted"] += 1

            # Track distribution stats
            src  = normalised.get("source", "unknown")
            dom  = normalised.get("domain", "unknown")
            diff = normalised.get("difficulty", -1)

            stats["by_source"][src]   = stats["by_source"].get(src, 0) + 1
            stats["by_domain"][dom]   = stats["by_domain"].get(dom, 0) + 1
            stats["by_difficulty"][diff] = stats["by_difficulty"].get(diff, 0) + 1

    if not all_entries:
        print("[ERROR] No entries to write after normalisation and deduplication.")
        return stats

    # ── Write JSONL output ────────────────────────────────────────────
    jsonl_path = f"{output_path}.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for entry in all_entries:
            f.write(json.dumps(entry) + "\n")
    print(f"\n[OUTPUT] JSONL → {jsonl_path}  ({len(all_entries)} entries)")

    # ── Write Parquet output ──────────────────────────────────────────
    if PARQUET_AVAILABLE:
        parquet_path = f"{output_path}.parquet"
        df    = pd.DataFrame(all_entries)
        table = pa.Table.from_pandas(df)
        pq.write_table(table, parquet_path)
        print(f"[OUTPUT] Parquet → {parquet_path}")
    else:
        print("[WARN] Parquet output skipped (pandas/pyarrow not available).")

    # ── Write merge report ────────────────────────────────────────────
    report_path = f"{output_path}_merge_report.txt"
    sep  = "=" * 55
    lines = [
        sep,
        "  TEAM 4 — UNIVERSAL SCHEMA MERGE REPORT",
        f"  Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  Mode      : {mode.upper()}",
        sep,
        "",
        f"  Input files    : {len(input_files)}",
        f"  Total loaded   : {stats['total_loaded']}",
        f"  Schema failures: {stats['schema_failures']}",
        f"  Duplicates     : {stats['duplicates']}",
        f"  Final entries  : {stats['total_accepted']}",
        "",
        "BY SOURCE",
        "-" * 35,
    ]
    for src, count in sorted(stats["by_source"].items()):
        lines.append(f"  {src:<20} {count}")

    lines += ["", "BY DOMAIN", "-" * 35]
    for dom, count in sorted(stats["by_domain"].items()):
        lines.append(f"  {dom:<20} {count}")

    lines += ["", "BY DIFFICULTY LEVEL", "-" * 35]
    for diff, count in sorted(stats["by_difficulty"].items(), key=lambda x: str(x[0])):
        lines.append(f"  Level {str(diff):<14} {count}")

    lines += ["", sep]
    report_text = "\n".join(lines)

    with open(report_path, "w") as f:
        f.write(report_text)

    print("\n" + report_text)
    print(f"[OUTPUT] Report → {report_path}")

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Team 4 — Universal Schema Merger"
    )
    parser.add_argument(
        "--inputs", nargs="+",
        help="Paths to accepted_data.jsonl files from each team"
    )
    parser.add_argument(
        "--scan",
        help="Scan a directory recursively for accepted_data.jsonl files"
    )
    parser.add_argument(
        "--output", required=True,
        help="Output path prefix e.g. merged/final_dataset"
    )
    parser.add_argument(
        "--mode", choices=["sft", "rl"], default="sft",
        help="Output schema: sft (default) or rl"
    )
    args = parser.parse_args()

    # Collect input files
    input_files = []
    if args.scan:
        input_files = scan_for_accepted(args.scan)
    if args.inputs:
        input_files += args.inputs

    if not input_files:
        print("[ERROR] No input files specified. Use --inputs or --scan.")
        exit(1)

    merge(input_files, args.output, args.mode)
