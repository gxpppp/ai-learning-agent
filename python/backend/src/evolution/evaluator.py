"""Evaluator — scores agent responses against the rubric using LLM-as-judge."""

from __future__ import annotations

import json
import os

RUBRIC_DIMENSIONS = {
    "accuracy": {"weight": 0.35, "prompt": "Is the answer factually correct? Any hallucinations?"},
    "conciseness": {"weight": 0.20, "prompt": "Is it the right length? No filler or unnecessary words?"},
    "action_taken": {"weight": 0.20, "prompt": "Did the agent actually DO something (use tools) or just talk?"},
    "tone": {"weight": 0.10, "prompt": "Is the tone warm but efficient? Not corporate, not robotic?"},
    "tool_choice": {"weight": 0.15, "prompt": "Were the right tools chosen in the right order?"},
}


def load_test_suite(vault_path: str) -> dict:
    path = os.path.join(vault_path, ".ai-tutor", "evolution", "EVALS", "test_suite_v1.json")
    if not os.path.exists(path):
        # Fallback to source directory
        path = os.path.join(os.path.dirname(__file__), "EVALS", "test_suite_v1.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_judge_prompt(response: str) -> str:
    """Build LLM-as-judge scoring prompt."""
    dims = "\n".join(
        f"- **{name}** ({float(d['weight'])*100:.0f}%): {d['prompt']}"  # type: ignore[arg-type]
        for name, d in RUBRIC_DIMENSIONS.items()
    )
    return f"""Score the following agent response on 5 dimensions. Give a score 0-10 for each.

Dimensions:
{dims}

Response to evaluate:
---
{response}
---

Output ONLY valid JSON: {{"accuracy": X, "conciseness": X, "action_taken": X, "tone": X, "tool_choice": X}}"""


def calculate_score(scores: dict[str, float]) -> float:
    """Calculate weighted total score."""
    total = 0.0
    for dim, info in RUBRIC_DIMENSIONS.items():
        total += scores.get(dim, 5.0) * float(info["weight"])  # type: ignore[arg-type]
    return round(total, 2)


async def evaluate_response(
    response_text: str,
    judge_llm,
) -> tuple[dict[str, float], float]:
    """Score a single response. Returns (dimension_scores, weighted_total)."""
    prompt = build_judge_prompt(response_text)
    resp = await judge_llm.async_client.chat.completions.create(
        model=judge_llm.model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=200,
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        scores: dict[str, float] = json.loads(raw)
    except json.JSONDecodeError:
        scores = {d: 5.0 for d in RUBRIC_DIMENSIONS}

    total = calculate_score(scores)
    return scores, total
