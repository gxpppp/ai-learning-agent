"""Mutation engine — generates prompt variants using 5 mutation operators."""

from __future__ import annotations

import uuid
from typing import Any


MUTATION_OPERATORS = {
    "shorten": "Delete >30% of redundant words while preserving core instructions.",
    "negative_space": "Rephrase positive rules as negative-space boundaries (e.g., 'Do X' → 'You must not skip X').",
    "add_example": "Insert a 1-shot example of a correct agent interaction.",
    "reorder": "Reorder instructions by priority — most important first.",
    "parameterize": "Replace vague instructions with measurable ones (e.g., 'be helpful' → 'call at least 1 tool per response').",
}


def get_operators() -> list[str]:
    return list(MUTATION_OPERATORS.keys())


def build_mutation_prompt(current_prompt: str, operators: list[str]) -> str:
    """Build a prompt that tells an LLM to apply operators to the current prompt."""
    op_desc = "\n".join(f"- **{op}**: {MUTATION_OPERATORS[op]}" for op in operators)
    return f"""You are a prompt engineer. Improve the following agent system prompt by applying these mutation operators:

{op_desc}

IMPORTANT: Apply ALL operators simultaneously. Output ONLY the improved prompt text — no markdown headers, no explanations, no 'Here is the improved prompt:'. Just the raw prompt text.

Current prompt:
---
{current_prompt}
---"""


async def generate_variants(
    current_prompt: str,
    num_variants: int = 5,
) -> list[dict[str, Any]]:
    """Generate N prompt variants using diverse operator combinations."""
    import random
    all_ops = get_operators()
    variants: list[dict[str, Any]] = []
    used_combos: set[str] = set()

    for _ in range(num_variants):
        n_ops = min(2 + random.randint(0, 2), len(all_ops))
        combo: tuple[str, ...]
        while True:
            combo = tuple(sorted(random.sample(all_ops, n_ops)))
            name = "+".join(combo)
            if name not in used_combos:
                used_combos.add(name)
                break

        v = {
            "id": f"v{uuid.uuid4().hex[:6]}",
            "operators": list(combo),
            "operator_name": name,
            "prompt": "",  # Filled by LLM call
        }
        variants.append(v)

    return variants
