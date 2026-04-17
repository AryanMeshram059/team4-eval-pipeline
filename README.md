# Team 4: Data Evaluation Pipeline

A comprehensive evaluation system that validates data quality for code, math, and reasoning tasks before they enter the training corpus.

## Project Overview

The Team 4 Evaluation Pipeline validates generated data from all teams using four independent validators:

1. **Math Verifier** - Checks mathematical answers against ground truth using symbolic comparison
2. **Code Evaluator** - Tests code correctness using LiveCodeBench and APPS metrics  
3. **Shepherd Critic** - Analyzes reasoning quality for logical consistency
4. **Safety Checker** - Scans code for security vulnerabilities

## Installation

### Prerequisites
- Python 3.8+ (3.10+ recommended)
- Linux/Mac (Windows with WSL supported)
- GPU recommended for Shepherd model (optional)

### Steps

1. **Clone the repository:**
```bash
git clone https://github.com/AryanMeshram059/team4-eval-pipeline.git
cd team4-eval-pipeline
```

2. **Create virtual environment:**
```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# OR using conda
conda create -n team4 python=3.10
conda activate team4
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Verify installation:**
```bash
python -c "from evaluators.math_verifier import MathVerifier; print('✓ OK')"
python -c "from evaluators.code_evaluator import CodeEvaluator; print('✓ OK')"
python -c "from evaluators.shepherd_critic import ShepherdCritic; print('✓ OK')"
python -c "from evaluators.safety_checker import SafetyChecker; print('✓ OK')"
```

## Dependencies

Key dependencies (see `requirements.txt` for complete list):

- `torch>=1.13.0` - PyTorch for model inference
- `transformers>=4.30.0` - HuggingFace transformers (Shepherd model)
- `math-verify>=0.1.0` - Mathematical answer verification
- `pandas>=1.3.0` - Data processing
- `numpy>=1.21.0` - Numerical computing
- `tqdm>=4.62.0` - Progress bars
- `timeout-decorator>=0.5.0` - Safe code execution timeouts

## Running the Code

### Basic Evaluation
```bash
python evaluate.py \
    --input data/sample_input.jsonl \
    --output data/results/
```

### Input Format (JSONL)
```json
{
  "prompt": "What is 2+2?",
  "solution": "<think>2+2 is 4</think>\n<answer>4</answer>",
  "ground_truth": "4",
  "domain": "math",
  "sub_domain": "arithmetic",
  "difficulty": 1
}
```

### Output Files
- `accepted_data.jsonl` - Verified entries ready for training
- `rejected_data.jsonl` - Entries that failed validation with reasons
- `evaluation_report.txt` - Summary statistics
- `eval_log_<timestamp>.jsonl` - Complete audit trail

### Advanced Examples

**Evaluate specific components only:**
```bash
python evaluate.py \
    --input data/sample.jsonl \
    --output results/ \
    --skip-math --skip-code --skip-safety
```

**Merge multiple datasets:**
```bash
python merge_datasets.py \
    --scan /path/to/datasets/ \
    --output merged_dataset/ \
    --mode sft
```

**Compute statistics:**
```bash
python compute_dataset_statistics.py
```

## Project Structure

```
team4-eval-pipeline/
├── README.md
├── TASKS.md                    # Detailed task documentation
├── requirements.txt
├── evaluate.py                 # Main entry point
├── merge_datasets.py          # Dataset merger
├── compute_dataset_statistics.py
├── evaluators/                # 4 validators
│   ├── math_verifier.py
│   ├── code_evaluator.py
│   ├── shepherd_critic.py
│   └── safety_checker.py
├── utils/
│   ├── logger.py
│   └── reporter.py
├── tools/                     # External tools
│   ├── LiveCodeBench/
│   ├── Shepherd/
│   └── synthetic-data-generators/
└── data/                      # Data directories
```

## Processed Datasets

### Datasets Converted & Integrated
The following team datasets have been successfully converted to the universal schema and are available in `data/converted/`:

**Team 1 - Chat & General Data:**
- ✅ `team1_multiturn.jsonl` - Multi-turn chat conversations
- ✅ `team1_general_multiturn.jsonl` - General multi-turn instructions

**Team 2 - Code & Math Data:**
- ✅ `team2_deepseek.jsonl` - Code generation from DeepSeek
- ✅ `team2_deepseek_math.jsonl` - Mathematical problems
- ✅ `team2_math_clean.jsonl` - Cleaned math dataset

**Team 3 - Reasoning Data:**
- ✅ `team3_official_fixed.jsonl` - Official reasoning dataset
- ✅ `team3_daman_fixed.jsonl` - Daman's reasoning dataset
- ✅ `team3_archit_fixed.jsonl` - Archit's reasoning dataset
- ✅ `team3_physicswallah.jsonl` - PhysicsWallah content

**Team 4+ - Evolution & Extended Data:**
- ✅ `evolv_math.jsonl` - Evolved mathematical problems
- ✅ `evolv_code.jsonl` - Evolved code problems
- ✅ `evolv_reasoning.jsonl` - Evolved reasoning tasks
- ✅ `evolv_nl.jsonl` - Evolved natural language
- ✅ `kimi_omni_math.jsonl` - Kimi Omni math data
- ✅ `kimi_s1k.jsonl` - Kimi S1K dataset
- ✅ `kimi_calculator_tool.jsonl` - Kimi calculator tool data
- ✅ `kimi_limo.jsonl` - Kimi Limo dataset

**Sample Data:**
- ✅ `sample_input.jsonl` - Example data for testing
- ✅ `code_chat_format.jsonl` - Code in chat format

### Available Raw Datasets (Not Yet Evaluated)

**Chat Data:**
- `Chat/SFT/UltraInteract_sft/0000_sft.parquet` (164MB) - Multi-turn chat data

**Code Data:**
- `Code/SFT/mbpp/data/mbpp.jsonl` - MBPP benchmark
- `Code/SFT/Code-Feedback/Code-Feedback.jsonl` - Code feedback dataset
- `Code/SFT/code_instructions_120k_alpaca/` (parquet) - 120k instruction pairs
- `Code/SFT/code-act/data/` - Code action dataset

**Reasoning Data:**
- `Reasoning/SFT/OpenThought-2/` (34GB) - 38 parquet files with extensive reasoning traces

**Safety Data:**
- `Safety/SFT/aya_redteaming/` (3.5MB) - Multi-language safety/adversarial data
  - aya_eng.jsonl, aya_arb.jsonl, aya_hin.jsonl, aya_tgl.jsonl, aya_srp.jsonl

## Remaining Work

### ⏳ Pending Evaluation Tasks

1. **Batch Evaluate Raw Datasets**
   - [ ] Process Chat/SFT/UltraInteract_sft (164MB)
   - [ ] Process Code/SFT/MBPP (benchmark suite)
   - [ ] Process Code/SFT/Code-Feedback
   - [ ] Process Code/SFT/code_instructions_120k
   - [ ] Process Reasoning/SFT/OpenThought-2 (34GB - may need batching)
   - [ ] Process Safety/SFT/aya_redteaming (multi-language safety)

2. **Generate Final Training Corpus**
   - [ ] Merge all accepted datasets with universal schema
   - [ ] Remove duplicates and near-duplicates
   - [ ] Compute final statistics (size, distribution, quality metrics)
   - [ ] Create balanced subsets if needed (train/val/test splits)

3. **Generate Comprehensive Reports**
   - [ ] Per-team evaluation report
   - [ ] Cross-team quality comparison
   - [ ] Domain-wise distribution analysis (math/code/reasoning/safety)
   - [ ] Difficulty distribution analysis
   - [ ] Pass/rejection rate breakdown

4. **Quality Assurance**
   - [ ] Sample validation (manual review of 1-2% of data)
   - [ ] Distribution shift analysis
   - [ ] Outlier detection and handling
   - [ ] Final corpus audit

### 📊 Current Status Summary
- **Datasets Integrated:** 17 converted datasets
- **Data Processed:** ~1.7GB in data/ directory
- **Evaluation Status:** Core pipeline complete, awaiting batch processing
- **Raw Datasets Ready:** 8+ additional sources (34GB+ total)

## License

MIT License - See LICENSE file for details
