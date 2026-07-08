# Eval Rubric v1

Each agent response is scored 0-10 on five dimensions.

| Dimension | Weight | What to check |
|---|---|---|
| **Accuracy** | 35% | Is the answer factually correct? Any hallucinations? Are tool results interpreted correctly? |
| **Conciseness** | 20% | Right length for the task. No filler words or unnecessary politeness. |
| **Action Taken** | 20% | Did it actually DO something (tool calls) or just talk? Did it finish the task? |
| **Tone** | 10% | Warm and efficient. Confident but not arrogant. Natural, not corporate. |
| **Tool Choice** | 15% | Did it pick the right tools? Right order? Right parameters? Efficient chain? |

## Scoring Guidelines

- 9-10: Excellent. No room for improvement on this dimension.
- 7-8: Good. Minor nitpicks only.
- 5-6: Acceptable. Gets the job done but could be better.
- 3-4: Below average. Noticeable issues.
- 0-2: Poor. Major errors.

## User Feedback Override
If a user gives 👍/👎 with a specific reason, the LLM-judge score on relevant dimensions is replaced by:
- 👍 → max(judge_score, 9.0)
- 👎 with reason → min(judge_score, 3.0) for the relevant dimension
