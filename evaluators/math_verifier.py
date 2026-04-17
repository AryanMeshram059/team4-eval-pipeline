"""
Math Verification — evaluators/math_verifier.py
================================================
Uses the HuggingFace Math-Verify library to:
  1. Extract the final answer from the model's solution string.
  2. Normalise LaTeX expressions.
  3. Compare symbolically against the ground truth.
"""

import re

try:
    from math_verify import verify, parse
    MATH_VERIFY_AVAILABLE = True
    print("[math_verifier] math-verify loaded successfully.")
except ImportError:
    MATH_VERIFY_AVAILABLE = False
    print("[WARN] math-verify not found. Falling back to string comparison.")


def _extract_answer(text: str) -> str:
    """
    Pull the final answer out of a model response.
    Priority:
      1. Content inside <answer>...</answer> tags
      2. Content after the closing </think> tag
      3. Last non-empty line (handles hybrid solutions where
         code block comes first and answer is on the last line)
      4. The whole text (last resort)
    """
    # 1. Explicit <answer> tag
    answer_match = re.search(r"<answer>(.*?)</answer>", text, re.DOTALL)
    if answer_match:
        return answer_match.group(1).strip()

    # 2. Everything after </think>
    think_split = re.split(r"</think>", text, maxsplit=1)
    if len(think_split) == 2:
        after_think = think_split[1].strip()
        if after_think:
            return after_think

    # 3. If solution contains a code block, take the last non-empty
    #    non-code line as the answer (handles hybrid entries)
    if "```" in text:
        lines = text.split("\n")
        non_code_lines = []
        in_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_block = not in_block
                continue
            if not in_block and line.strip():
                non_code_lines.append(line.strip())
        if non_code_lines:
            return non_code_lines[-1]

    # 4. Fallback: return full text stripped
    return text.strip()


def _normalise(s: str) -> str:
    """Normalise a string for fallback comparison."""
    s = s.strip().lower()
    s = re.sub(r"[\$\\]", "", s)        # remove LaTeX markers
    s = re.sub(r"\s+", "", s)           # remove all whitespace
    s = re.sub(r"[,;.]$", "", s)        # remove trailing punctuation
    return s


class MathVerifier:
    """
    Verifies whether a generated math solution matches the ground truth.

    Usage:
        verifier = MathVerifier()
        passed, detail = verifier.verify(solution_text, ground_truth_text)
    """

    def __init__(self):
        self.available = MATH_VERIFY_AVAILABLE

    def verify(self, solution: str, ground_truth: str) -> tuple[bool, str]:
        """
        Returns:
            (True,  "PASS")       if answer matches ground truth
            (False, <reason>)     if it does not
        """
        extracted = _extract_answer(solution)

        if not extracted:
            return False, "Could not extract an answer from the solution."

        if self.available:
            return self._verify_with_library(extracted, ground_truth)
        else:
            return self._verify_string_fallback(extracted, ground_truth)

    def _verify_with_library(
        self, extracted: str, ground_truth: str
    ) -> tuple[bool, str]:
        try:
            parsed_pred  = parse(extracted)
            parsed_truth = parse(ground_truth)
            result       = verify(parsed_pred, parsed_truth)
            if result:
                return True, "PASS"
            else:
                # Try string fallback before giving up
                fb_pass, fb_detail = self._verify_string_fallback(
                    extracted, ground_truth
                )
                if fb_pass:
                    return True, "PASS (string match fallback)"
                return False, (
                    f"Answer '{extracted[:80]}' != "
                    f"ground truth '{ground_truth[:80]}'"
                )
        except Exception:
            return self._verify_string_fallback(extracted, ground_truth)

    def _verify_string_fallback(
        self, extracted: str, ground_truth: str
    ) -> tuple[bool, str]:
        n_pred  = _normalise(extracted)
        n_truth = _normalise(ground_truth)
        if n_pred == n_truth:
            return True, "PASS (string match)"
        # Also try checking if ground truth appears anywhere in extracted
        if n_truth in n_pred or n_pred in n_truth:
            return True, "PASS (substring match)"
        return False, f"Mismatch: '{n_pred[:60]}' != '{n_truth[:60]}'"
