from typing import Annotated, List, Dict, TypedDict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from agents import (
    arun_moderator,
    arun_researcher,
    arun_pro_agent,
    arun_opponent_agent,
    arun_fact_checker,
    arun_verdict_agent,
)

def append_list(a: list, b: list) -> list:
    if not a: return b
    if not b: return a
    return a + b

class DebateState(TypedDict):
    debate_id: str
    topic: str
    rules: str
    current_round: int
    max_rounds: int
    conversation: Annotated[List[Dict], append_list]
    fact_checking_results: Annotated[List[Dict], append_list]
    search_queries: Annotated[List[str], append_list]
    background_context: str
    verdict: str
    verdict_data: Dict[str, Any]

def route_from_moderator(state: DebateState):
    if state["current_round"] > state["max_rounds"]:
        return "verdict_agent"
    if state["current_round"] == 0:
        return "researcher"
    return "pro_agent"

def increment_round(state: DebateState) -> dict:
    return {"current_round": state["current_round"] + 1}

def build_debate_graph(checkpointer=None):
    builder = StateGraph(DebateState)

    builder.add_node("moderator", arun_moderator)
    builder.add_node("researcher", arun_researcher)
    builder.add_node("pro_agent", arun_pro_agent)
    builder.add_node("opponent_agent", arun_opponent_agent)
    builder.add_node("fact_checker", arun_fact_checker)
    builder.add_node("increment_round", increment_round)
    builder.add_node("verdict_agent", arun_verdict_agent)

    builder.add_edge(START, "moderator")
    builder.add_conditional_edges(
        "moderator",
        route_from_moderator,
        {"researcher": "researcher", "pro_agent": "pro_agent", "verdict_agent": "verdict_agent"},
    )
    builder.add_edge("researcher", "pro_agent")
    builder.add_edge("pro_agent", "opponent_agent")
    builder.add_edge("opponent_agent", "fact_checker")
    builder.add_edge("fact_checker", "increment_round")
    builder.add_edge("increment_round", "moderator")
    builder.add_edge("verdict_agent", END)

    active_checkpointer = checkpointer if checkpointer is not None else InMemorySaver()
    return builder.compile(checkpointer=active_checkpointer)


debate_graph = build_debate_graph()
