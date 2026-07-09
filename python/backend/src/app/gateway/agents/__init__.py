"""Agent role definitions for the multi-agent system."""

from app.gateway.agents.orchestrator import ORCHESTRATOR_DEFINITION, ORCHESTRATOR_PROMPT
from app.gateway.agents.operator import OPERATOR_DEFINITION, OPERATOR_PROMPT
from app.gateway.agents.searcher import SEARCHER_DEFINITION, SEARCHER_PROMPT
from app.gateway.agents.verifier import VERIFIER_DEFINITION, VERIFIER_PROMPT

AGENT_DEFINITIONS = {
    "orchestrator": ORCHESTRATOR_DEFINITION,
    "searcher": SEARCHER_DEFINITION,
    "operator": OPERATOR_DEFINITION,
    "verifier": VERIFIER_DEFINITION,
}
