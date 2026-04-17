"""
Shepherd Reasoning Critic — evaluators/shepherd_critic.py
==========================================================
Loads the Shepherd model (reciprocate/shepherd-7b) from HuggingFace
to critique <think> reasoning traces.

Shepherd was developed by Facebook Research and is specifically
fine-tuned to identify errors in LLM reasoning outputs across
6 error categories:
  - Arithmetic errors
  - Coherence and deduction errors
  - Consistency with context
  - Veracity errors
  - Redundancy
  - Commonsense errors

Repo:  tools/Shepherd/ (cloned, contains training data + notebooks only)
Model: https://huggingface.co/reciprocate/shepherd-7b
Paper: https://arxiv.org/abs/2308.04592
"""

import re
import os

# ── Try to load transformers + torch ─────────────────────────────────
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("[WARN] transformers/torch not installed. Using heuristic Shepherd fallback.")

SHEPHERD_MODEL_ID = "gavin124/shepherd-finetuned-v2"

# ── Shepherd prompt template ──────────────────────────────────────────
# This mirrors the format used in Shepherd's own evaluation notebook
# (tools/Shepherd/notebook/) which prompts the model to critique a response
# given the original question.
SHEPHERD_PROMPT = """\
Given the following question and a candidate answer with reasoning, \
identify any errors in the reasoning. Look for:
- Arithmetic errors
- Logical gaps or missing deduction steps
- Steps that contradict each other
- Incorrect conclusions
- Missing commonsense knowledge
- Claims inconsistent with the question

Question:
{problem}

Reasoning Trace:
{think_trace}

Final Answer:
{solution}

Critique:"""


# ── Heuristic fallback critic ─────────────────────────────────────────
# Used when GPU/model is unavailable.
# Mirrors Shepherd's 6 error categories with rule-based detection.

_ERROR_PATTERNS = [
    # Arithmetic errors
    (r"\b\d+\s*[\+\-\*\/]\s*\d+\s*=\s*\d+",         "arithmetic_check"),
    # Contradictions
    (r"(therefore|thus|hence).{0,80}(wrong|incorrect|false)", "contradiction"),
    # Uncertainty (weak reasoning)
    (r"\b(maybe|perhaps|possibly|I think|not sure)\b", "uncertain_reasoning"),
    # Missing steps
    (r"(skip|shortcut|assume without|left as exercise)",  "missing_step"),
    # Division by zero risk
    (r"divide\s+by\s+zero|denominator.*=.*0",             "division_by_zero"),
]

_POSITIVE_SIGNALS = [
    r"\bstep\s+\d+\b",
    r"\btherefore\b",
    r"\bbecause\b",
    r"\bsince\b",
    r"\bsubstitut",
    r"\bsimplif",
    r"\bexpand",
    r"\bfactor",
    r"\bprove\b",
    r"\bverif",
    r"\bcheck\b",
]

# Known arithmetic mistake patterns e.g. "-3 + -4 = 1"
_ARITH_MISTAKE = re.compile(
    r"(-?\d+)\s*\+\s*(-?\d+)\s*=\s*(-?\d+)"
)


def _check_arithmetic(text: str) -> list[str]:
    """Check simple addition expressions for correctness."""
    mistakes = []
    for match in _ARITH_MISTAKE.finditer(text):
        a, b, c = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if a + b != c:
            mistakes.append(
                f"Arithmetic error: {a} + {b} = {c} (should be {a+b})"
            )
    return mistakes


def _heuristic_critique(
    problem: str, think_trace: str, solution: str
) -> tuple[bool, float, str]:
    """
    Rule-based fallback when Shepherd model is unavailable.
    Maps to Shepherd's 6 error categories.
    Returns (critique_pass, rqs_score 0.0-1.0, critique_text).
    """
    if not think_trace or len(think_trace.strip()) < 20:
        return False, 0.0, "Think trace is empty or too short to evaluate."

    issues = []
    score  = 1.0

    # Check arithmetic
    arith_errors = _check_arithmetic(think_trace)
    for err in arith_errors:
        issues.append(f"[Arithmetic] {err}")
        score -= 0.25

    # Check other error patterns
    for pattern, label in _ERROR_PATTERNS:
        if re.search(pattern, think_trace, re.IGNORECASE):
            if label == "arithmetic_check":
                continue   # already handled above
            issues.append(f"[{label}] Pattern detected in reasoning trace")
            score -= 0.15

    # Reward positive reasoning signals
    positive_hits = sum(
        1 for p in _POSITIVE_SIGNALS
        if re.search(p, think_trace, re.IGNORECASE)
    )
    score += min(positive_hits * 0.05, 0.20)

    # Penalise very short traces
    word_count = len(think_trace.split())
    if word_count < 15:
        issues.append("[Coherence] Reasoning trace too brief to be meaningful")
        score -= 0.30

    score  = max(0.0, min(1.0, score))
    passed = (score >= 0.5) and (len(issues) == 0)
    detail = "; ".join(issues) if issues else "No issues found (heuristic)"

    return passed, round(score, 3), f"[Heuristic Shepherd] {detail}"


# ── Shepherd model inference ──────────────────────────────────────────

def _run_shepherd(
    tokenizer, model, device: str,
    problem: str, think_trace: str, solution: str
) -> tuple[bool, float, str]:
    """
    Run the actual Shepherd model to critique the reasoning trace.
    """
    prompt = SHEPHERD_PROMPT.format(
        problem    = problem[:600],
        think_trace= think_trace[:2000],
        solution   = solution[:400],
    )

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=2048,
    ).to(device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=False,        # greedy for reproducibility
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )

    # Decode only the newly generated tokens (not the prompt)
    new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
    critique   = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    # Score based on Shepherd's critique content
    # Map to Shepherd's 6 error categories
    error_keywords = {
        "arithmetic":   ["arithmetic", "calculation", "math error", "incorrect number"],
        "coherence":    ["does not follow", "gap", "missing step", "contradiction", "illogical"],
        "consistency":  ["inconsistent", "contradicts", "does not match"],
        "veracity":     ["incorrect", "wrong", "false", "inaccurate", "error"],
        "redundancy":   ["redundant", "repeated", "unnecessary"],
        "commonsense":  ["common sense", "obvious", "basic knowledge"],
    }

    n_issues = 0
    found_categories = []
    critique_lower = critique.lower()

    for category, keywords in error_keywords.items():
        if any(kw in critique_lower for kw in keywords):
            n_issues += 1
            found_categories.append(category)

    # "No error" or very short critiques with no keywords = good trace
    no_error_signals = ["no error", "correct", "well-reasoned", "accurate", "looks good"]
    is_clean = any(sig in critique_lower for sig in no_error_signals)

    if is_clean and n_issues == 0:
        rqs    = 1.0
        passed = True
    else:
        rqs    = max(0.0, 1.0 - n_issues * 0.18)
        passed = n_issues == 0

    detail = (
        f"Shepherd critique — errors found in: {found_categories}" 
        if found_categories 
        else "Shepherd critique — no errors found"
    )

    return passed, round(rqs, 3), f"{detail} | Raw: {critique[:300]}"


# ── Public class ──────────────────────────────────────────────────────

class ShepherdCritic:
    """
    Critiques <think> reasoning traces using Shepherd (reciprocate/shepherd-7b)
    or a heuristic fallback if the model is unavailable.

    Usage:
        critic = ShepherdCritic()
        passed, rqs, detail = critic.critique(problem, think_trace, solution)

    Args:
        use_model     (bool):  Try to load the Shepherd model. Set False to force heuristic.
        rqs_threshold (float): Minimum RQS to accept a trace (0.0-1.0). Default 0.5.
    """

    def __init__(self, use_model: bool = True, rqs_threshold: float = 0.5):
        self.rqs_threshold = rqs_threshold
        self.model         = None
        self.tokenizer     = None
        self.device        = None

        if use_model and TRANSFORMERS_AVAILABLE:
            self._load_model()
        elif not TRANSFORMERS_AVAILABLE:
            print("[ShepherdCritic] Running in heuristic mode (transformers unavailable).")
        else:
            print("[ShepherdCritic] Running in heuristic mode (use_model=False).")

    def _load_model(self):
        try:
            print(f"[ShepherdCritic] Loading {SHEPHERD_MODEL_ID} ...")
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"[ShepherdCritic] Using device: {self.device}")

            self.tokenizer = AutoTokenizer.from_pretrained(
                SHEPHERD_MODEL_ID,
                use_fast=True,
            )

            self.model = AutoModelForCausalLM.from_pretrained(
                SHEPHERD_MODEL_ID,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto",
            )
            self.model.eval()
            print(f"[ShepherdCritic] Model loaded successfully on {self.device}.")

        except Exception as e:
            print(f"[WARN] Could not load Shepherd model: {e}")
            print("[ShepherdCritic] Falling back to heuristic critic.")
            self.model     = None
            self.tokenizer = None

    def critique(
        self, problem: str, think_trace: str, solution: str
    ) -> tuple[bool, float, str]:
        """
        Critique a reasoning trace.

        Returns:
            passed (bool)   — True if reasoning quality is acceptable
            rqs    (float)  — Reasoning Quality Score (0.0 - 1.0)
            detail (str)    — Explanation of any issues found
        """
        if self.model is not None and self.tokenizer is not None:
            passed, rqs, detail = _run_shepherd(
                self.tokenizer, self.model, self.device,
                problem, think_trace, solution
            )
        else:
            passed, rqs, detail = _heuristic_critique(
                problem, think_trace, solution
            )

        # Apply RQS threshold — even if Shepherd says "pass",
        # reject if score is below threshold
        if rqs < self.rqs_threshold:
            passed = False

        return passed, rqs, detail
