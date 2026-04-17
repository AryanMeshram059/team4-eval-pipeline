#!/usr/bin/env python3
"""
Merge all accepted_data.jsonl files into three parquet files:
1. code_merged.parquet - Code-related datasets
2. math_merged.parquet - Math-related datasets
3. nl_merged.parquet - Natural language/reasoning datasets
"""

import json
import os
from pathlib import Path
import pandas as pd
from typing import List, Dict


def categorize_datasets():
    """
    Categorize datasets into code, math, and NL categories.
    """
    categories = {
        'code': [
            'apps_code',
            'code_auto',
            'code_chat_format',
            'evolv_code',
        ],
        'math': [
            'evolv_math',
            'kimi_calculator_tool',
            'kimi_limo',
            'kimi_omni_math',
            'kimi_s1k',
            'kimi_telemath',
            'kimi_telemath.json',
            'numinamath_tir.json',
            'team3_archit_fixed.json',
            'team3_daman_fixed.json',
            'team3_fathom.json',
            'team3_official_fixed.json',
            'team3_physicswallah.json',
        ],
        'nl': [
            'evolv_nl',
            'evolv_reasoning',
            'science_reasoning.json',
            'team1_general_multiturn.json',
            'team1_multiturn.json',
            'team2_deepseek.json',
        ]
    }
    return categories


def sanitize_string(value):
    """
    Sanitize string values to remove problematic characters.
    """
    if isinstance(value, str):
        # Remove null bytes and other problematic characters
        value = value.replace('\x00', '')
        # Ensure proper string encoding
        try:
            value.encode('utf-8')
        except UnicodeEncodeError:
            value = value.encode('utf-8', errors='ignore').decode('utf-8')
    return value


def sanitize_object(obj):
    """
    Recursively sanitize object fields.
    """
    if isinstance(obj, dict):
        return {k: sanitize_object(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_object(item) for item in obj]
    elif isinstance(obj, str):
        return sanitize_string(obj)
    return obj


def read_jsonl_file(file_path: str) -> List[Dict]:
    """
    Read a JSONL file and return list of parsed JSON objects.
    Robust error handling for malformed JSON.
    """
    if not os.path.exists(file_path):
        return []
    
    rows = []
    skipped_lines = 0
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    # Try to parse JSON
                    row = json.loads(line)
                    # Sanitize the data
                    row = sanitize_object(row)
                    row['_source_dataset'] = os.path.basename(os.path.dirname(file_path))
                    rows.append(row)
                except json.JSONDecodeError as e:
                    skipped_lines += 1
                    # Try to recover by looking for common issues
                    if len(skipped_lines) <= 3:  # Only print first 3 warnings per file
                        print(f"  Warning: Skipped malformed line {line_num} in {os.path.basename(file_path)}")
                    continue
    except Exception as e:
        print(f"Warning: Error reading {file_path}: {e}")
    
    if skipped_lines > 3:
        print(f"  ... and {skipped_lines - 3} more malformed lines skipped")
    
    return rows


def merge_category(results_dir: str, category_datasets: List[str], category_name: str) -> pd.DataFrame:
    """
    Merge all accepted data from datasets in a category.
    """
    all_rows = []
    total_rows = 0
    skipped_datasets = []
    
    # Columns to remove (unnecessary evaluation metadata)
    columns_to_drop = [
        'eval_math_pass', 'eval_code_pass', 'eval_code_metrics', 'eval_code_metrics_apps', 'eval_code_metrics_full',
        'eval_safety_pass', 'eval_shepherd_pass', 'eval_rqs', 
        'eval_rejection_reason', 'eval_final_verdict'
    ]
    
    for dataset_name in category_datasets:
        dataset_path = os.path.join(results_dir, dataset_name)
        accepted_file = os.path.join(dataset_path, 'accepted_data.jsonl')
        
        if not os.path.exists(accepted_file):
            skipped_datasets.append(dataset_name)
            continue
        
        rows = read_jsonl_file(accepted_file)
        all_rows.extend(rows)
        total_rows += len(rows)
        print(f"  ✓ {dataset_name}: {len(rows)} rows")
    
    # Create DataFrame
    if all_rows:
        df = pd.DataFrame(all_rows)
        
        # Sanitize all string columns to ensure valid parquet encoding
        for col in df.columns:
            if df[col].dtype == 'object':
                # Handle lists/arrays by converting to JSON strings
                df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (list, dict)) else sanitize_string(x) if isinstance(x, str) else x)
        
        # Drop unnecessary columns
        cols_to_drop = [col for col in columns_to_drop if col in df.columns]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
        
        # Fill NaN values with empty strings for string columns
        string_cols = df.select_dtypes(include=['object']).columns
        for col in string_cols:
            df[col] = df[col].fillna('')
        
        print(f"\n{category_name.upper()} Summary:")
        print(f"  Total rows: {len(df)}")
        print(f"  Datasets merged: {len(category_datasets) - len(skipped_datasets)}")
        if skipped_datasets:
            print(f"  Skipped (no accepted_data.jsonl): {', '.join(skipped_datasets)}")
        print(f"  Columns retained: {list(df.columns)}")
        return df
    else:
        print(f"\n{category_name.upper()}: No data found!")
        return pd.DataFrame()


def main():
    results_dir = '/projects/data/datasets/code_post_training_data/team4_eval_pipeline/data/results'
    output_dir = '/projects/data/datasets/code_post_training_data/team4_eval_pipeline/data/merged_parquet'
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Get dataset categories
    categories = categorize_datasets()
    
    print("=" * 100)
    print("MERGING ACCEPTED DATA BY CATEGORY")
    print("=" * 100)
    
    # Process each category
    results = {}
    
    for category, datasets in categories.items():
        print(f"\n{category.upper()} Datasets:")
        df = merge_category(results_dir, datasets, category)
        results[category] = df
    
    # Save to parquet files
    print("\n" + "=" * 100)
    print("SAVING PARQUET FILES")
    print("=" * 100)
    
    for category, df in results.items():
        if len(df) > 0:
            try:
                output_file = os.path.join(output_dir, f'{category}_merged.parquet')
                
                # Convert all object columns to strings for parquet compatibility
                df_copy = df.copy()
                for col in df_copy.select_dtypes(include=['object']).columns:
                    df_copy[col] = df_copy[col].astype(str)
                
                df_copy.to_parquet(output_file, index=False, compression='snappy', engine='pyarrow')
                print(f"\n✓ Saved: {output_file}")
                print(f"  Rows: {len(df_copy)}")
                print(f"  File size: {os.path.getsize(output_file) / (1024**3):.2f} GB")
            except Exception as e:
                print(f"\n✗ Error saving {category}_merged.parquet: {e}")
        else:
            print(f"\n✗ {category.upper()}: No data to save")
    
    # Print overall summary
    print("\n" + "=" * 100)
    print("FINAL SUMMARY")
    print("=" * 100)
    
    total_all = sum(len(df) for df in results.values())
    for category, df in results.items():
        if len(df) > 0:
            percentage = (len(df) / total_all) * 100 if total_all > 0 else 0
            print(f"{category.upper():15} {len(df):,} rows ({percentage:.1f}%)")
    
    print(f"{'TOTAL':15} {total_all:,} rows")
    print(f"\nOutput directory: {output_dir}")


if __name__ == '__main__':
    main()
