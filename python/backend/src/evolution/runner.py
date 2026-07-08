"""Evolution runner — orchestrates mutation → evaluation → deploy cycle.

Usage: python -m evolution.runner
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from app.config import ACTIVE_CHAT_MODEL, ACTIVE_PROVIDER_ID, OBSIDIAN_VAULT_PATH


def _evolution_dir() -> str:
    return os.path.join(OBSIDIAN_VAULT_PATH, ".ai-tutor", "evolution")


def _load_active_prompt() -> str:
    path = os.path.join(_evolution_dir(), "VARIANTS", "active.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    # Default: return agent system prompt
    return """You are an AI learning assistant with full control over the user's Obsidian vault.
Use tools to help the user organize, search, create, and analyze notes.
Be proactive, transparent, and efficient."""


def _save_prompt(variant_id: str, prompt: str) -> str:
    variants_dir = os.path.join(_evolution_dir(), "VARIANTS")
    os.makedirs(variants_dir, exist_ok=True)
    path = os.path.join(variants_dir, f"{variant_id}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(prompt)
    return path


def _deploy_prompt(prompt: str) -> None:
    """Replace active prompt. The running agent picks it up on next session."""
    os.makedirs(os.path.join(_evolution_dir(), "VARIANTS"), exist_ok=True)
    path = os.path.join(_evolution_dir(), "VARIANTS", "active.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(prompt)


def _log_mutation(entry: dict) -> None:
    mutations_dir = os.path.join(_evolution_dir(), "MUTATIONS")
    os.makedirs(mutations_dir, exist_ok=True)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    path = os.path.join(mutations_dir, f"{today}.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _log_history(line: str) -> None:
    path = os.path.join(_evolution_dir(), "HISTORY.md")
    os.makedirs(_evolution_dir(), exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"- {ts}: {line}\n")


async def run_evolution_cycle() -> dict[str, Any]:
    """Run one full evolution cycle and return summary."""
    from app.services.llm_manager import llm_manager
    from evolution.evaluator import evaluate_response, load_test_suite
    from evolution.mutator import build_mutation_prompt, generate_variants

    if not llm_manager:
        return {"error": "LLM Manager not initialized"}

    judge = llm_manager.get_chat_client(ACTIVE_PROVIDER_ID, ACTIVE_CHAT_MODEL)
    current = _load_active_prompt()
    test_suite = load_test_suite(OBSIDIAN_VAULT_PATH)
    variants = await generate_variants(current, num_variants=5)

    scores: dict[str, float] = {}
    best_id = ""
    best_score = 0.0

    for v in variants:
        ops = v["operators"]
        mutation_prompt = build_mutation_prompt(current, ops)

        # Generate variant via LLM
        resp = await judge.async_client.chat.completions.create(
            model=ACTIVE_CHAT_MODEL,
            messages=[{"role": "user", "content": mutation_prompt}],
            temperature=0.8,
            max_tokens=1000,
        )
        v["prompt"] = resp.choices[0].message.content or ""
        _save_prompt(v["id"], v["prompt"])

        # Score variant (simplified: score the prompt itself)
        # In production, you'd run the agent with each prompt and score the output
        # For now, score the prompt quality via the judge
        judge_score, total = await evaluate_response(
            f"New system prompt:\n{v['prompt']}\n\nTask: Rate this prompt's clarity and actionability.",
            judge,
        )
        scores[v["id"]] = total
        if total > best_score:
            best_score = total
            best_id = v["id"]

        _log_mutation({
            "id": v["id"],
            "operators": v["operator_name"],
            "score": total,
            "timestamp": datetime.now(UTC).isoformat(),
        })

    current_score = scores.get("current", 5.0)
    if best_score > current_score * 1.05 and best_id:
        _deploy_prompt(variants[0]["prompt"] if best_id == variants[0]["id"] else current)
        _log_history(f"Deployed {best_id} (score {best_score}, +{round(best_score - current_score, 2)})")
        status = "deployed"
    else:
        _log_history(f"No deployment (best={best_score}, current={current_score})")
        status = "no_change"

    return {
        "status": status,
        "variants_tested": len(variants),
        "best_score": best_score,
        "best_variant": best_id,
        "timestamp": datetime.now(UTC).isoformat(),
    }
