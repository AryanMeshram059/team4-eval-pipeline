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

## License

MIT License - See LICENSE file for details
