# Dataset Evaluation Statistics

This script computes comprehensive statistics across all evaluation datasets in the team4_eval_pipeline.

## Features

The script (`compute_dataset_statistics.py`) provides:

1. **Per-Dataset Statistics**:
   - Total row count (accepted + rejected)
   - Accepted vs rejected breakdown
   - Reasoning row count (rows where "think" field is non-empty)
   - Multi-turn row count (detected via dataset name keywords)
   - Synthetic dataset detection

2. **Dataset Detection**:
   - **Multi-turn datasets**: Contains keywords like "multiturn", "multi_turn", "numina", "chat", "conversation"
   - **Synthetic datasets**: Contains keywords like "science_reasoning", "gpt", "generated", "synthetic", "evolv"
   - **Reasoning data**: Detected by checking if the "think" field contains non-empty content

3. **Overall Summary**:
   - Total rows across all datasets
   - Totals for accepted/rejected/reasoning rows
   - Breakdown by synthetic vs non-synthetic
   - Breakdown by multi-turn vs single-turn

## Usage

```bash
cd /projects/data/datasets/code_post_training_data/team4_eval_pipeline
python compute_dataset_statistics.py
```

## Key Results (from latest run)

- **Total Datasets**: 23
- **Total Rows**: 295,153
- **Accepted**: 251,316 (85%)
- **Rejected**: 43,837 (15%)
- **Reasoning Rows**: 192,982 (65%)
- **Synthetic Rows**: 107,563 (36%)
- **Multi-turn Rows**: 139,891 (47%)

**Synthetic Datasets (5)**: evolv_code, evolv_math, evolv_nl, evolv_reasoning, science_reasoning.json

**Multi-turn Datasets (4)**: code_chat_format, team1_general_multiturn.json, team1_multiturn.json, team2_deepseek.json (partial)

## File Structure

Each dataset folder contains:
- `accepted_data.jsonl` - JSONL file with accepted examples
- `rejected_data.jsonl` - JSONL file with rejected examples
- `evaluation_report.txt` - Text report of evaluation results
- `eval_log_*.jsonl` - Evaluation logs

## Error Handling

The script robustly handles:
- Missing files (returns 0 rows)
- Malformed JSON lines (logs warning and continues)
- Empty lines in JSONL files
- Missing fields in JSON objects

## JSONL Data Format

Each row contains fields like:
```json
{
  "prompt": "...",
  "think": "...",
  "solution": "...",
  "ground_truth": "...",
  "eval_math_pass": null,
  "eval_code_pass": null,
  "eval_final_verdict": "PASS",
  ...
}
```

Reasoning is detected by checking if the `think` field contains non-empty, non-whitespace content.
