# Team 4: Data Evaluation Pipeline 🔍

**Final Evaluation Pipeline for Code, Math, and Reasoning Data Quality Assessment**

> This repository contains the evaluation system developed by Team 4 for the course project. It validates generated data from other teams before they enter the final training corpus, using mathematical verification, code execution testing, reasoning critique, and safety analysis.

## 📋 Project Overview

The Team 4 Evaluation Pipeline is a comprehensive data quality assurance system designed to:

1. **Verify Mathematical Solutions** - Uses symbolic computation (math-verify) to validate mathematical answers against ground truth
2. **Test Code Correctness** - Executes code against unit tests and competitive programming benchmarks (LiveCodeBench + APPS metric)
3. **Critique Reasoning Traces** - Analyzes logical consistency in LLM reasoning outputs using the Shepherd model
4. **Check Code Safety** - Scans code for security vulnerabilities using the Code-Safety-Bench benchmark

### Team Responsibility

Per the course specification (Mar 17), **Team 4 is responsible for**:
- ✅ Evaluating data quality from all teams
- ✅ Establishing a universal schema for dataset merging
- ✅ Computing dataset statistics across all evaluation results
- ✅ Maintaining the final training corpus integrity

---

## 🎯 Key Components

### 1. **Main Evaluation Pipeline** (`evaluate.py`)
The central entry point that orchestrates all evaluators.

**Usage:**
```bash
python evaluate.py \
    --input data/sample_input.jsonl \
    --output data/results/ \
    --log-level INFO
```

**Input Format (JSONL):**
```json
{
  "prompt": "What is 2+2?",
  "solution": "<think>2+2 is 4</think>\n<answer>4</answer>",
  "ground_truth": "4",
  "domain": "math",
  "sub_domain": "arithmetic",
  "difficulty": 1,
  "unit_tests": ["assert solution == 4"],
  "source": "team2"
}
```

**Output Files:**
- `accepted_data.jsonl` - Clean, verified entries ready for training
- `rejected_data.jsonl` - Entries that failed evaluation with rejection reasons
- `evaluation_report.txt` - Summary statistics and pass rates
- `eval_log_<timestamp>.jsonl` - Complete audit trail with detailed scores

### 2. **Math Verifier** (`evaluators/math_verifier.py`)
Validates mathematical solutions using symbolic comparison.

**Supported Features:**
- LaTeX expression normalization
- Final answer extraction from reasoning traces
- Symbolic comparison (not just string matching)
- Fallback string comparison when library unavailable

**Evaluated Fields:**
- Answer correctness (pass/fail)
- Extraction confidence score
- Normalization quality metrics

### 3. **Code Evaluator** (`evaluators/code_evaluator.py`)
Executes code against test cases using two metrics:

#### **LiveCodeBench**
- Evaluates competitive programming problems
- Computes pass@1, pass@3, pass@5 metrics
- Supports multiple code generations
- Reference: https://github.com/LiveCodeBench/LiveCodeBench

#### **APPS Metric**
- Runs code against hidden test cases
- Pass only if ALL tests succeed
- Measures actual execution correctness
- Reference: https://huggingface.co/spaces/codeparrot/apps_metric

**Test Format Support:**
```json
{
  "unit_tests": ["assert solution(3) == 9", "assert solution(0) == 0"],
  "input_output": [{"input": "3", "output": "9"}],
  "timeout_seconds": 5
}
```

### 4. **Shepherd Reasoning Critic** (`evaluators/shepherd_critic.py`)
Analyzes logical consistency in reasoning traces using Facebook Research's Shepherd model.

**Error Categories Detected:**
- Arithmetic errors
- Logical gaps / deduction errors
- Consistency violations
- Veracity errors
- Redundancy
- Commonsense violations

**Model:** `gavin124/shepherd-finetuned-v2` (7B parameters, on HuggingFace)

**Features:**
- GPU acceleration with torch
- Heuristic fallback for CPU-only systems
- Reasoning Quality Score (RQS)

### 5. **Safety Checker** (`evaluators/safety_checker.py`)
Scans code for security vulnerabilities using Code-Safety-Bench patterns.

**Vulnerability Categories:**
- SQL Injection
- Cross-Site Scripting (XSS)
- API Endpoint Manipulation
- Race Conditions
- Buffer Overflow
- Path Traversal
- Command Injection
- More...

**Analysis Methods:**
- Regex pattern matching
- AST-based Python code analysis
- Vulnerability benchmark database

### 6. **Dataset Statistics** (`compute_dataset_statistics.py`)
Aggregates statistics across all evaluation datasets.

**Usage:**
```bash
python compute_dataset_statistics.py
```

**Outputs:**
- Per-dataset acceptance rates
- Reasoning vs non-reasoning breakdown
- Synthetic vs real data split
- Multi-turn vs single-turn distribution
- Total row counts

**Latest Results (23 datasets):**
| Metric | Count | Percentage |
|--------|-------|-----------|
| Total Rows | 295,153 | - |
| Accepted | 251,316 | 85% |
| Rejected | 43,837 | 15% |
| Reasoning | 192,982 | 65% |
| Synthetic | 107,563 | 36% |
| Multi-turn | 139,891 | 47% |

### 7. **Dataset Merger** (`merge_datasets.py`)
Merges accepted data from all teams into a universal schema.

**Schemas Supported:**

**SFT Schema:**
```json
{
  "prompt": "string",
  "response": "<think>...</think>\n[final answer]",
  "domain": "math | code | hybrid | nl",
  "sub_domain": "string",
  "difficulty": 0-4,
  "source": "string (team name)",
  "verified_by": ["list of validators"],
  "eval_rqs": 0.0-1.0
}
```

**RL Schema:**
```json
{
  "prompt": "string",
  "ground_truth": "string",
  "domain": "string",
  "difficulty": 0-4,
  "reward_format": 0.0-1.0,
  "reward_accuracy": 0.0-1.0,
  "source": "string"
}
```

**Usage:**
```bash
# Merge specific teams
python merge_datasets.py \
    --inputs team1/accepted_data.jsonl team2/accepted_data.jsonl \
    --output merged/final_dataset \
    --mode sft

# Auto-scan directory
python merge_datasets.py \
    --scan /projects/data/datasets/code_post_training_data/ \
    --output merged/final_dataset \
    --mode sft
```

---

## 🚀 Installation & Setup

### Prerequisites
- **Python:** 3.8+ (3.10+ recommended)
- **OS:** Linux/Mac (Windows with WSL supported)
- **Hardware:** CPU works; GPU (CUDA) strongly recommended for Shepherd model

### Step 1: Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/team4-eval-pipeline.git
cd team4-eval-pipeline
```

### Step 2: Create Virtual Environment
```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# OR using conda
conda create -n team4 python=3.10
conda activate team4
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Download External Tools (Optional but Recommended)

#### LiveCodeBench
```bash
# Already included in tools/LiveCodeBench/
# If needed, clone manually:
git clone https://github.com/LiveCodeBench/LiveCodeBench.git tools/LiveCodeBench
```

#### Shepherd Model
```bash
# Downloads automatically on first use via HuggingFace transformers
# Or pre-download:
python -c "from transformers import AutoModelForCausalLM, AutoTokenizer; \
  AutoModelForCausalLM.from_pretrained('gavin124/shepherd-finetuned-v2'); \
  AutoTokenizer.from_pretrained('gavin124/shepherd-finetuned-v2')"
```

### Step 5: Verify Installation
```bash
# Test imports
python -c "from evaluators.math_verifier import MathVerifier; print('✓ Math Verifier OK')"
python -c "from evaluators.code_evaluator import CodeEvaluator; print('✓ Code Evaluator OK')"
python -c "from evaluators.shepherd_critic import ShepherdCritic; print('✓ Shepherd Critic OK')"
python -c "from evaluators.safety_checker import SafetyChecker; print('✓ Safety Checker OK')"
```

---

## 📖 Usage Examples

### Example 1: Evaluate a Single JSONL File
```bash
python evaluate.py \
    --input data/sample_input.jsonl \
    --output data/results/ \
    --log-level DEBUG
```

### Example 2: Evaluate with Specific Validations Only
```bash
python evaluate.py \
    --input data/sample.jsonl \
    --output results/ \
    --skip-math \
    --skip-code \
    --skip-safety
    # This will only run Shepherd reasoning critique
```

### Example 3: Process Multiple Teams' Data
```bash
# Evaluate Team 1's data
python evaluate.py --input team1_data.jsonl --output team1_results/

# Evaluate Team 2's data
python evaluate.py --input team2_data.jsonl --output team2_results/

# Merge all accepted data
python merge_datasets.py \
    --scan . \
    --output final_merged/ \
    --mode sft
```

### Example 4: Compute Statistics
```bash
python compute_dataset_statistics.py
# Output: Summary of all 23 datasets with breakdowns
```

---

## 📊 Project Structure

```
team4-eval-pipeline/
├── README.md                          # This file
├── TASKS.md                           # Task documentation & status
├── requirements.txt                   # Python dependencies
├── LICENSE                            # MIT License
│
├── evaluate.py                        # Main evaluation entry point
├── merge_datasets.py                  # Universal schema merger
├── compute_dataset_statistics.py      # Statistics aggregator
│
├── evaluators/                        # Core evaluation modules
│   ├── __init__.py
│   ├── math_verifier.py              # Mathematical answer validation
│   ├── code_evaluator.py             # Code execution + LiveCodeBench + APPS
│   ├── apps_evaluator.py             # APPS metric implementation
│   ├── shepherd_critic.py            # Reasoning quality critique
│   └── safety_checker.py             # Code vulnerability scanning
│
├── utils/                             # Utility modules
│   ├── __init__.py
│   ├── logger.py                     # Logging & audit trails
│   └── reporter.py                   # Result reporting & statistics
│
├── tools/                             # External tools & benchmarks
│   ├── LiveCodeBench/                # Competitive programming benchmark
│   ├── Shepherd/                     # Shepherd model repo (reference)
│   └── synthetic-data-generators/    # Code-Safety-Bench vulnerability DB
│
└── data/                              # Data directories (created at runtime)
    ├── input/                        # Sample input JSONL files
    ├── results/                      # Evaluation outputs
    └── logs/                         # Execution logs
```

---

## 🔄 Evaluation Workflow

```
┌─────────────────────┐
│  Input JSONL File   │
│ (team1/2/3 data)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────┐
│      Load & Validate Entries        │
│  (check required fields present)     │
└──────────┬──────────────────────────┘
           │
      ┌────┴────┬────────┬─────────┐
      │          │        │         │
      ▼          ▼        ▼         ▼
  ┌────────┐ ┌──────┐ ┌────────┐ ┌──────┐
  │ Math   │ │ Code │ │Shepherd│ │Safety│
  │Verify  │ │Eval  │ │ Critic │ │Check │
  └────┬───┘ └──┬───┘ └───┬────┘ └──┬───┘
       │        │         │        │
       └────────┴─────────┴────────┘
               │
               ▼
      ┌──────────────────┐
      │  Aggregate Score │
      │  (all validators)│
      └────────┬─────────┘
               │
        ┌──────┴──────┐
        │             │
        ▼             ▼
   ┌────────┐   ┌─────────┐
   │ACCEPTED│   │ REJECTED│
   │ Data   │   │  Data   │
   └────────┘   └─────────┘
        │             │
        └─────┬───────┘
              │
              ▼
    ┌──────────────────────┐
    │  Generate Reports:   │
    │  - accepted.jsonl    │
    │  - rejected.jsonl    │
    │  - eval_report.txt   │
    │  - eval_log.jsonl    │
    └──────────────────────┘
```

---

## 🧪 Testing & Verification

### Run Unit Tests
```bash
pytest tests/ -v
```

### Test Math Verifier
```bash
python -c "
from evaluators.math_verifier import MathVerifier
mv = MathVerifier()
passed, msg = mv.verify('The answer is 4', '4')
print(f'Test passed: {passed}')
"
```

### Test Code Evaluator
```bash
python -c "
from evaluators.code_evaluator import CodeEvaluator
ce = CodeEvaluator()
code = 'def add(a, b): return a + b'
tests = ['assert add(2, 2) == 4', 'assert add(0, 0) == 0']
passed, score = ce.evaluate_code(code, tests)
print(f'Code passed: {passed}, Score: {score}')
"
```

### Test Shepherd Critic
```bash
python -c "
from evaluators.shepherd_critic import ShepherdCritic
sc = ShepherdCritic()
critique = sc.critique(
    problem='What is 2+2?',
    thinking='2+2 is clearly 5',
    solution='5'
)
print(f'Quality Score: {critique.get(\"quality_score\", \"N/A\")}')
"
```

---

## 📋 Supported Data Domains

| Domain | Sub-domains | Validators Used |
|--------|-------------|-----------------|
| **math** | algebra, calculus, geometry, arithmetic | Math Verifier + Shepherd |
| **code** | python, java, cpp, javascript, sql | Code Evaluator + Safety Checker |
| **nl** | summarization, translation, qa | Shepherd Critic + Safety Checker |
| **hybrid** | math + code, reasoning + execution | All Validators |

---

## 📊 Evaluation Metrics

### For Math Entries
- ✅ **Pass/Fail** — Answer matches ground truth
- 📊 **Confidence** — Extraction confidence 0-1
- 🧠 **RQS Score** — Reasoning Quality Score (Shepherd)

### For Code Entries
- ✅ **Pass@1** — Passes on first attempt
- ✅ **Pass@3** — Passes within 3 attempts
- ✅ **Pass@5** — Passes within 5 attempts
- 🛡️ **Safety** — No vulnerabilities detected
- ⏱️ **Timeout** — Execution completes within limit

### For Reasoning (All Types)
- 🧠 **RQS Score** — 0-1, higher is better
- 🔍 **Error Detection** — Category of errors found
- 📝 **Critique Quality** — Detailed feedback

---

## 🔒 Safety & Security

This repository:
- ✅ Executes untrusted code in isolated environments with timeouts
- ✅ Scans all code against Code-Safety-Bench vulnerability database
- ✅ Validates mathematical expressions before evaluation
- ✅ Logs all evaluations for audit trails
- ✅ Never stores sensitive data or credentials

**Note:** Code execution happens in subprocess isolation. Always review unknown code before evaluation.

---

## 📝 Logging & Debugging

### Enable Debug Logging
```bash
python evaluate.py --input data.jsonl --output results/ --log-level DEBUG
```

### View Evaluation Logs
```bash
tail -f data/results/eval_log_*.jsonl | python -m json.tool
```

### Check Rejection Reasons
```bash
# Count rejections by reason
python -c "
import json
with open('results/rejected_data.jsonl') as f:
    reasons = {}
    for line in f:
        entry = json.loads(line)
        reason = entry.get('rejection_reason', 'Unknown')
        reasons[reason] = reasons.get(reason, 0) + 1
    for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True):
        print(f'{reason}: {count}')
"
```

---

## 🤝 Contributing

To contribute improvements:

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and test thoroughly
3. Commit with descriptive messages: `git commit -m "Add [feature name]"`
4. Push and create a Pull Request: `git push origin feature/your-feature`
5. Ensure all tests pass before merging

---

## 📄 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) file for details.

---

## 📞 Support & Questions

For questions about the evaluation pipeline:
- Check [TASKS.md](TASKS.md) for task status and completed work
- Review [README_STATISTICS.md](README_STATISTICS.md) for dataset statistics
- Check inline code documentation in evaluators/
- Contact Team 4 lead

---

## 🎓 Course Context

**Course:** [Course Name]  
**Team:** Team 4  
**Responsibility:** Data Quality Evaluation & Schema Unification  
**Submission Date:** [Insert Date]  
**Repository:** [Will be added on GitHub]

---

**Last Updated:** April 17, 2026  
**Status:** ✅ Ready for Evaluation
