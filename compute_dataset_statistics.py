#!/usr/bin/env python3
"""
Compute statistics across all evaluation datasets in the team4_eval_pipeline results directory.
"""

import json
import os
from pathlib import Path
from collections import defaultdict


def is_multi_turn_dataset(dataset_name):
    """
    Detect if a dataset is multi-turn based on naming conventions.
    """
    multi_turn_keywords = ['multiturn', 'multi_turn', 'numina', 'chat', 'conversation']
    return any(keyword in dataset_name.lower() for keyword in multi_turn_keywords)


def is_synthetic_dataset(dataset_name):
    """
    Detect if a dataset is synthetic based on naming conventions.
    """
    synthetic_keywords = ['science_reasoning', 'gpt', 'generated', 'synthetic', 'evolv']
    return any(keyword in dataset_name.lower() for keyword in synthetic_keywords)


def is_reasoning_row(row):
    """
    Check if a row contains reasoning data.
    A reasoning row has a non-empty 'think' field.
    """
    think_field = row.get('think', '')
    # Check if think field exists and is non-empty (not just whitespace)
    return bool(think_field and str(think_field).strip())


def read_jsonl_file(file_path):
    """
    Read a JSONL file and return list of parsed JSON objects.
    Returns empty list if file doesn't exist or has errors.
    """
    if not os.path.exists(file_path):
        return []
    
    rows = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                try:
                    row = json.loads(line)
                    rows.append(row)
                except json.JSONDecodeError as e:
                    print(f"Warning: Failed to parse line {line_num} in {file_path}: {e}")
                    continue
    except Exception as e:
        print(f"Warning: Failed to read {file_path}: {e}")
    
    return rows


def process_dataset(dataset_path):
    """
    Process a single dataset folder and return statistics.
    """
    dataset_name = os.path.basename(dataset_path)
    
    # Paths to data files
    accepted_file = os.path.join(dataset_path, 'accepted_data.jsonl')
    rejected_file = os.path.join(dataset_path, 'rejected_data.jsonl')
    
    # Read data
    accepted_rows = read_jsonl_file(accepted_file)
    rejected_rows = read_jsonl_file(rejected_file)
    
    all_rows = accepted_rows + rejected_rows
    
    # Calculate statistics
    total_rows = len(all_rows)
    accepted_count = len(accepted_rows)
    rejected_count = len(rejected_rows)
    
    # Count reasoning rows
    reasoning_count = sum(1 for row in all_rows if is_reasoning_row(row))
    
    # Count multi-turn rows
    multi_turn_count = sum(1 for row in all_rows 
                          if is_multi_turn_dataset(dataset_name) or 
                             'conversational' in json.dumps(row, default=str).lower())
    
    # Check if synthetic
    is_synthetic = is_synthetic_dataset(dataset_name)
    
    return {
        'name': dataset_name,
        'total_rows': total_rows,
        'accepted': accepted_count,
        'rejected': rejected_count,
        'reasoning_rows': reasoning_count,
        'multi_turn_rows': multi_turn_count,
        'is_synthetic': is_synthetic
    }


def main():
    """
    Main function to compute statistics across all datasets.
    """
    results_dir = '/projects/data/datasets/code_post_training_data/team4_eval_pipeline/data/results'
    
    # Verify the results directory exists
    if not os.path.isdir(results_dir):
        print(f"Error: Results directory not found: {results_dir}")
        return
    
    # Get all dataset folders (exclude files)
    dataset_folders = []
    for item in sorted(os.listdir(results_dir)):
        item_path = os.path.join(results_dir, item)
        if os.path.isdir(item_path):
            dataset_folders.append(item_path)
    
    if not dataset_folders:
        print("No dataset folders found in results directory.")
        return
    
    # Process each dataset
    all_stats = []
    for dataset_path in dataset_folders:
        try:
            stats = process_dataset(dataset_path)
            all_stats.append(stats)
        except Exception as e:
            print(f"Error processing {os.path.basename(dataset_path)}: {e}")
            continue
    
    # Print per-dataset statistics
    print("=" * 100)
    print("PER-DATASET STATISTICS")
    print("=" * 100)
    
    for stats in all_stats:
        print(f"\nDataset: {stats['name']}")
        print(f"  Total rows: {stats['total_rows']}")
        print(f"  Accepted: {stats['accepted']}")
        print(f"  Rejected: {stats['rejected']}")
        print(f"  Multi-turn rows: {stats['multi_turn_rows']}")
        print(f"  Reasoning rows: {stats['reasoning_rows']}")
        print(f"  Synthetic: {'Yes' if stats['is_synthetic'] else 'No'}")
    
    # Calculate overall statistics
    total_rows_all = sum(s['total_rows'] for s in all_stats)
    total_accepted_all = sum(s['accepted'] for s in all_stats)
    total_rejected_all = sum(s['rejected'] for s in all_stats)
    total_reasoning_all = sum(s['reasoning_rows'] for s in all_stats)
    total_synthetic_all = sum(s['total_rows'] for s in all_stats if s['is_synthetic'])
    total_multi_turn_all = sum(s['multi_turn_rows'] for s in all_stats)
    
    # Print overall summary
    print("\n" + "=" * 100)
    print("OVERALL SUMMARY")
    print("=" * 100)
    print(f"Total datasets: {len(all_stats)}")
    print(f"Total rows: {total_rows_all}")
    print(f"Total accepted: {total_accepted_all}")
    print(f"Total rejected: {total_rejected_all}")
    print(f"Total multi-turn rows: {total_multi_turn_all}")
    print(f"Total reasoning rows: {total_reasoning_all}")
    print(f"Total synthetic rows: {total_synthetic_all}")
    print(f"Synthetic datasets: {sum(1 for s in all_stats if s['is_synthetic'])}")
    
    # Print breakdown by synthetic vs non-synthetic
    print("\n" + "-" * 100)
    print("SYNTHETIC VS NON-SYNTHETIC BREAKDOWN")
    print("-" * 100)
    
    synthetic_stats = [s for s in all_stats if s['is_synthetic']]
    non_synthetic_stats = [s for s in all_stats if not s['is_synthetic']]
    
    print(f"\nSynthetic datasets: {len(synthetic_stats)}")
    print(f"  Total rows: {sum(s['total_rows'] for s in synthetic_stats)}")
    print(f"  Total reasoning rows: {sum(s['reasoning_rows'] for s in synthetic_stats)}")
    
    print(f"\nNon-synthetic datasets: {len(non_synthetic_stats)}")
    print(f"  Total rows: {sum(s['total_rows'] for s in non_synthetic_stats)}")
    print(f"  Total reasoning rows: {sum(s['reasoning_rows'] for s in non_synthetic_stats)}")
    
    # Print multi-turn breakdown
    multi_turn_datasets = [s for s in all_stats if is_multi_turn_dataset(s['name'])]
    non_multi_turn_datasets = [s for s in all_stats if not is_multi_turn_dataset(s['name'])]
    
    print("\n" + "-" * 100)
    print("MULTI-TURN VS SINGLE-TURN BREAKDOWN")
    print("-" * 100)
    
    print(f"\nMulti-turn datasets: {len(multi_turn_datasets)}")
    print(f"  Total rows: {sum(s['total_rows'] for s in multi_turn_datasets)}")
    
    print(f"\nSingle-turn datasets: {len(non_multi_turn_datasets)}")
    print(f"  Total rows: {sum(s['total_rows'] for s in non_multi_turn_datasets)}")


if __name__ == '__main__':
    main()
