from typing import Annotated, List, Dict, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
import operator

from agents import run_moderator, run_researcher, run_pro_agent, run_opponent_agent, run_fact_checker, run_verdict_agent

def append_list(a: list, b: list) -> list:
    if not a: return b
    if not b: return a
    return a + b

class DebateState(TypedDict):
    topic: str
    rules: str
    current_round: int
    max_rounds: int
    conversation: Annotated[List[Dict], append_list]
    fact_checking_results: Annotated[List[Dict], append_list]
    search_queries: Annotated[List[str], append_list]
    background_context: str
    verdict: str

def route_from_moderator(state: DebateState):
    if state["current_round"] > state["max_rounds"]:
        return "verdict_agent"
    if state["current_round"] == 0:
        return "researcher"
    return "pro_agent"

def increment_round(state: DebateState) -> dict:
    return {"current_round": state["current_round"] + 1}

# Create Graph
builder = StateGraph(DebateState)

# Add Nodes
builder.add_node("moderator", run_moderator)
builder.add_node("researcher", run_researcher)
builder.add_node("pro_agent", run_pro_agent)
builder.add_node("opponent_agent", run_opponent_agent)
builder.add_node("fact_checker", run_fact_checker)
builder.add_node("increment_round", increment_round)
builder.add_node("verdict_agent", run_verdict_agent)

# Add Edges
builder.add_edge(START, "moderator")
builder.add_conditional_edges("moderator", route_from_moderator, {"researcher": "researcher", "pro_agent": "pro_agent", "verdict_agent": "verdict_agent"})
builder.add_edge("researcher", "pro_agent")
builder.add_edge("pro_agent", "opponent_agent")
builder.add_edge("opponent_agent", "fact_checker")
builder.add_edge("fact_checker", "increment_round")
builder.add_edge("increment_round", "moderator")
builder.add_edge("verdict_agent", END)

# Compile Graph
debate_graph = builder.compile()
