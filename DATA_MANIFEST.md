# Data Manifest - Team 4 Evaluation Pipeline

## ⚠️ Large Datasets Not in GitHub

The final merged datasets (1.7GB) are stored locally and **not** included in this GitHub repository due to size constraints. This is standard practice for data-heavy ML projects.

## 📍 Local Data Location

```
/projects/data/datasets/code_post_training_data/team4_eval_pipeline/data/
```

## 📊 Dataset Summary

### Processed & Converted Datasets (30+ files)

**Team 1 - Chat & General:**
- `team1_multiturn.jsonl` (121M) - Multi-turn conversations
- `team1_general_multiturn.jsonl` (5.7M) - General instructions
- `team1_math_servicenow_1.jsonl` (9.5M) - Math problems batch 1
- `team1_math_servicenow_2.jsonl` (9.5M) - Math problems batch 2
- `team1_numina.jsonl` (0B) - Numina dataset

**Team 2 - Code & Math:**
- `team2_deepseek.jsonl` - Code generation
- `team2_deepseek_math.jsonl` - Mathematical problems
- `team2_math_clean.jsonl` (15M) - Cleaned math dataset

**Team 3 - Reasoning:**
- `team3_official_fixed.jsonl` - Official reasoning dataset
- `team3_daman_fixed.jsonl` - Daman's reasoning dataset
- `team3_archit_fixed.jsonl` - Archit's reasoning dataset
- `team3_physicswallah.jsonl` - PhysicsWallah content
- `team3_fathom.jsonl` - Fathom dataset

**Evolution & Extended Data:**
- `evolv_math.jsonl` (4.8M) - Evolved mathematical problems
- `evolv_code.jsonl` (12M) - Evolved code problems
- `evolv_reasoning.jsonl` (5.5M) - Evolved reasoning tasks
- `evolv_nl.jsonl` (8.4M) - Evolved natural language
- `science_reasoning.jsonl` (31M) - Science reasoning dataset

**Kimi Variants:**
- `kimi_omni_math.jsonl` (241M) - Kimi Omni math data
- `kimi_s1k.jsonl` (46M) - Kimi S1K dataset
- `kimi_limo.jsonl` (43M) - Kimi Limo dataset
- `kimi_calculator_tool.jsonl` (2.2M) - Kimi calculator tool
- `kimi_telemath.jsonl` (30M) - Kimi TeleMath

**Other Sources:**
- `code_chat_format.jsonl` (24M) - Code in chat format
- `apps_code.jsonl` (42M) - APPS benchmark code
- `code_auto.jsonl` (462K) - Auto-generated code
- `team3_demo.jsonl` (3.1M) - Demo dataset
- `team3_jeebench.jsonl` (3.2M) - JEE benchmark
- `sample_input.jsonl` (4.7K) - Test sample

### Merged Formats
- `merged_parquet/code_merged.parquet` - Code domain merged
- `merged_parquet/math_merged.parquet` - Math domain merged
- `merged_parquet/nl_merged.parquet` - NL domain merged

### Evaluation Results
- `results/` - Contains evaluation outputs for each dataset:
  - `accepted_data.jsonl` - Passed validation
  - `rejected_data.jsonl` - Failed validation with reasons
  - `evaluation_report.txt` - Summary statistics
  - `eval_log_*.jsonl` - Detailed evaluation logs

## 📈 Statistics

- **Total Files:** 107 JSONL + parquet files
- **Total Size:** 1.7GB
- **Converted Datasets:** 30+
- **Evaluation Results:** 50+ directories with pass/fail analysis
- **Universal Schema:** Applied to all datasets

## 🔄 How to Access Data

To work with these datasets locally:

```bash
# Python
import json
with open('data/converted/team1_multiturn.jsonl') as f:
    for line in f:
        record = json.loads(line)
        # Process record
```

## 📤 For Sharing/Deployment

To share these datasets with evaluators or for production use, consider:

1. **Hugging Face Hub** - Upload to public/private datasets
2. **AWS S3** - Use S3 URLs in data loading
3. **Google Cloud Storage** - Similar cloud-based approach
4. **Compressed Archive** - Create `.tar.gz` for download
5. **Data API** - Build a service to serve data on demand

## 🔗 Related Files

- [README.md](README.md) - Main project documentation
- [TASKS.md](TASKS.md) - Detailed task completion summary
- [evaluate.py](evaluate.py) - Main evaluation pipeline
- [merge_datasets.py](merge_datasets.py) - Dataset merger utility
