from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langgraph.checkpoint.memory import InMemorySaver

from config.config import MAX_MODEL_CALLS_PER_RUN, hitl_enabled
from middlewares import AuditMiddleware, ProtectionMiddleware, HITLMiddleware
from models import build_chat_model
from memory import make_checkpointer
from tools import ALL_TOOLS
from prompts import build_system_prompt
from schemas import TurnSummary

def build_middleware(
    *,
    enable_hitl: bool
) -> list:
    """
    Harness layers, outermost first.

    1. model-call cap
    2. Audit log 
    3. payload guarding
    4. HITL on write/edit/run 
    """

    layers: list = [
        ModelCallLimitMiddleware(
            run_limit=MAX_MODEL_CALLS_PER_RUN,
            exit_behavior="end"
        ),
        AuditMiddleware(),
        ProtectionMiddleware()
    ]

    if enable_hitl:
        layers.append(HITLMiddleware())

    return layers

def build_agent(
    *,
    checkpointer: InMemorySaver | None = None,
    enable_hitl: bool | None = None,
    extra_guidance: str = "",
):
    model, _provider = build_chat_model()
    use_hitl = hitl_enabled() if enable_hitl is None else enable_hitl
    return create_agent(
        model=model,
        tools=ALL_TOOLS,
        system_prompt=build_system_prompt(extra_guidance=extra_guidance),
        middleware=build_middleware(enable_hitl=use_hitl),
        response_format=ProviderStrategy(TurnSummary),
        checkpointer=checkpointer or make_checkpointer(),
        name="Coding Agent",
    )