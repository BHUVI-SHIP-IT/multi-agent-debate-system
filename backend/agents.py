from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from database import query_knowledge_base, clear_knowledge_base, add_to_knowledge_base
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import json
import re
from typing import Dict, Any
from dotenv import load_dotenv
from tavily import TavilyClient
from settings import settings
from topic_cache import topic_context_cache

load_dotenv()
_tavily_api_key = os.getenv("TAVILY_API_KEY", "").strip()
tavily_client = TavilyClient(api_key=_tavily_api_key) if _tavily_api_key else None

# We'll use llama3 as the default local model
# Ensure you have it pulled locally: ollama run llama3.2
MODEL = settings.model_name
base_llm = ChatOllama(model=MODEL, base_url=settings.ollama_base_url, temperature=0.7)
strict_llm = ChatOllama(model=MODEL, base_url=settings.ollama_base_url, temperature=0.1)
NODE_EXECUTOR = ThreadPoolExecutor(max_workers=settings.node_executor_workers)

CRITERIA_WEIGHTS = {
    "argument_quality": 25,
    "evidence_use": 25,
    "rebuttal_effectiveness": 20,
    "factual_accuracy": 20,
    "clarity": 10,
}

FALSE_CLAIM_PENALTY = 8
REPEATED_PARTIAL_PENALTY = 3
TIE_THRESHOLD = 2

def _strip_role_prefix(text: str) -> str:
    """Remove any leading [ROLE] label the LLM may have echoed."""
    return re.sub(r'^\s*(\[[A-Z_\s]+\]\s*)+', '', text).strip()


def _extract_json_object(text: str) -> Dict[str, Any]:
    """Parse a JSON object even if the model wraps it in prose or code fences."""
    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start : end + 1]
        try:
            return json.loads(snippet)
        except Exception:
            return {}
    return {}


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _normalize_side_scores(raw_scores: Dict[str, Any]) -> Dict[str, float]:
    normalized: Dict[str, float] = {}
    for criterion, max_points in CRITERIA_WEIGHTS.items():
        value = _coerce_float(raw_scores.get(criterion, 0.0), 0.0)
        normalized[criterion] = min(max(value, 0.0), float(max_points))
    normalized["total"] = round(sum(normalized[c] for c in CRITERIA_WEIGHTS), 2)
    return normalized


def _empty_verdict_schema() -> Dict[str, Any]:
    return {
        "scores": {
            "pro": _normalize_side_scores({}),
            "opponent": _normalize_side_scores({}),
        },
        "winner": "tie",
        "rationale": "Insufficient signal; defaulting to tie.",
        "confidence": 50,
        "key_errors": {"pro": [], "opponent": []},
        "summary": "Debate complete with no clear edge.",
        "penalties": {
            "pro": {"false_claims": 0, "repeated_partial_true": 0, "points_deducted": 0},
            "opponent": {"false_claims": 0, "repeated_partial_true": 0, "points_deducted": 0},
        },
    }


def _build_fact_penalty_data(conversation: list) -> Dict[str, Dict[str, int]]:
    """
    Walk fact_checker turns and assign each judgment to the latest debating side.
    False claims are penalized directly; repeated Partially True claims are penalized.
    """
    penalties = {
        "pro": {"false_claims": 0, "partial_true": 0},
        "opponent": {"false_claims": 0, "partial_true": 0},
    }

    last_debater = None
    for msg in conversation:
        role = msg.get("role")
        content = (msg.get("content") or "").strip().lower()

        if role in {"pro", "opponent"}:
            last_debater = role
            continue

        if role != "fact_checker" or last_debater not in {"pro", "opponent"}:
            continue

        if content.startswith("false"):
            penalties[last_debater]["false_claims"] += 1
        elif content.startswith("partially true"):
            penalties[last_debater]["partial_true"] += 1

    return penalties


def _apply_penalties(verdict_data: Dict[str, Any], conversation: list) -> Dict[str, Any]:
    penalty_counts = _build_fact_penalty_data(conversation)
    scores = verdict_data["scores"]
    key_errors = verdict_data.setdefault("key_errors", {"pro": [], "opponent": []})

    for side in ("pro", "opponent"):
        false_claims = penalty_counts[side]["false_claims"]
        partial_true = penalty_counts[side]["partial_true"]
        repeated_partial = max(partial_true - 1, 0)
        deduction = false_claims * FALSE_CLAIM_PENALTY + repeated_partial * REPEATED_PARTIAL_PENALTY

        adjusted_total = max(_coerce_float(scores[side].get("total", 0.0)) - deduction, 0.0)
        scores[side]["total"] = round(adjusted_total, 2)

        verdict_data["penalties"][side] = {
            "false_claims": false_claims,
            "repeated_partial_true": repeated_partial,
            "points_deducted": deduction,
        }

        if false_claims > 0:
            key_errors.setdefault(side, []).append(
                f"{false_claims} claim(s) rated False by fact checker"
            )
        if repeated_partial > 0:
            key_errors.setdefault(side, []).append(
                f"{repeated_partial} repeated Partially True claim(s)"
            )

    pro_total = scores["pro"]["total"]
    opp_total = scores["opponent"]["total"]
    margin = round(abs(pro_total - opp_total), 2)

    if margin < TIE_THRESHOLD:
        verdict_data["winner"] = "tie"
    else:
        verdict_data["winner"] = "pro" if pro_total > opp_total else "opponent"

    model_conf = int(max(0, min(100, _coerce_float(verdict_data.get("confidence", 50), 50))))
    margin_conf = min(int(margin * 8), 40)
    verdict_data["confidence"] = min(95, max(35, model_conf // 2 + 30 + margin_conf))

    return verdict_data


def _normalize_verdict_payload(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    verdict_data = _empty_verdict_schema()

    raw_scores = raw_payload.get("scores", {}) if isinstance(raw_payload, dict) else {}
    pro_raw = raw_scores.get("pro", {}) if isinstance(raw_scores, dict) else {}
    opp_raw = raw_scores.get("opponent", {}) if isinstance(raw_scores, dict) else {}

    verdict_data["scores"]["pro"] = _normalize_side_scores(pro_raw)
    verdict_data["scores"]["opponent"] = _normalize_side_scores(opp_raw)

    winner = str(raw_payload.get("winner", "tie")).strip().lower() if isinstance(raw_payload, dict) else "tie"
    verdict_data["winner"] = winner if winner in {"pro", "opponent", "tie"} else "tie"

    verdict_data["rationale"] = str(raw_payload.get("rationale", verdict_data["rationale"])) if isinstance(raw_payload, dict) else verdict_data["rationale"]
    verdict_data["summary"] = str(raw_payload.get("summary", verdict_data["summary"])) if isinstance(raw_payload, dict) else verdict_data["summary"]

    confidence = int(max(0, min(100, _coerce_float(raw_payload.get("confidence", 50), 50)))) if isinstance(raw_payload, dict) else 50
    verdict_data["confidence"] = confidence

    key_errors = raw_payload.get("key_errors", {}) if isinstance(raw_payload, dict) else {}
    if isinstance(key_errors, dict):
        verdict_data["key_errors"] = {
            "pro": [str(item) for item in key_errors.get("pro", [])] if isinstance(key_errors.get("pro", []), list) else [],
            "opponent": [str(item) for item in key_errors.get("opponent", [])] if isinstance(key_errors.get("opponent", []), list) else [],
        }

    return verdict_data


def _format_verdict_summary(verdict_data: Dict[str, Any]) -> str:
    scores = verdict_data["scores"]
    summary = verdict_data.get("summary", "")
    rationale = verdict_data.get("rationale", "")
    return (
        f"Winner: {verdict_data['winner'].upper()}\n"
        f"Score (Pro/Opponent): {scores['pro']['total']}/{scores['opponent']['total']}\n"
        f"Confidence: {verdict_data['confidence']}\n"
        f"Summary: {summary}\n"
        f"Rationale: {rationale}"
    )

def run_moderator(state: dict) -> dict:
    topic = state.get("topic", "")
    current_round = state.get("current_round", 0)
    max_rounds = state.get("max_rounds", 3)
    
    if current_round == 0:
        rules = f"A formal debate on: {topic}. There will be {max_rounds} rounds."
        return {
            "rules": rules,
            "conversation": [{"role": "moderator", "content": f"The debate begins. Topic: {topic}. Pro Agent, please start."}]
        }
    else:
        # Moderator doesn't say much between turns unless necessary
        return {}

def run_researcher(state: dict) -> dict:
    topic = state["topic"]
    debate_id = state.get("debate_id", "default")

    cached_context = topic_context_cache.get(topic)
    if cached_context:
        clear_knowledge_base(debate_id)
        add_to_knowledge_base(cached_context.split("\n"), debate_id)
        return {
            "search_queries": [topic],
            "background_context": cached_context,
            "conversation": [{"role": "researcher", "content": f"Loaded cached context for the debate:\n{cached_context}"}],
        }
    
    # Clear the knowledge base from the previous debate
    clear_knowledge_base(debate_id)
    
    try:
        if tavily_client is None:
            raise RuntimeError("Tavily API key not configured")

        # Perform a web search to gather recent news and context
        search_result = tavily_client.search(query=topic, search_depth="basic", max_results=3)
        context_snippets = [f"- {res['title']}: {res['content']}" for res in search_result.get("results", [])]
        
        # Add the fresh web snippets into the local Vector DB for fact checking
        if context_snippets:
            add_to_knowledge_base(context_snippets, debate_id)
            
        background_context = "\n".join(context_snippets)
        if not background_context:
            background_context = "No recent web results found."
        else:
            topic_context_cache.set(topic, background_context)
    except Exception as e:
        background_context = f"Failed to retrieve web search context: {str(e)}"
    
    return {
        "search_queries": [topic],
        "background_context": background_context,
        "conversation": [{"role": "researcher", "content": f"Gathered recent context for the debate:\n{background_context}"}]
    }

def run_pro_agent(state: dict) -> dict:
    topic = state["topic"]
    conversation = state.get("conversation", [])
    background_context = state.get("background_context", "")
    
    sys_msg = SystemMessage(content=(
        f"You are the Pro Agent in a formal debate. You strongly support the topic: '{topic}'.\n"
        f"Recent Context:\n{background_context}\n\n"
        "Give a concise 2-3 sentence argument FOR the topic. "
        "Do NOT start your response with any label such as [PRO], [OPPONENT], or any other tag. "
        "Respond ONLY with your argument."
    ))
    conv_summary = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in conversation
    )
    messages = [sys_msg, HumanMessage(content=f"Debate so far:\n{conv_summary}\n\nYour argument:")]
    response = base_llm.invoke(messages)
    return {"conversation": [{"role": "pro", "content": _strip_role_prefix(response.content)}]}

def run_opponent_agent(state: dict) -> dict:
    topic = state["topic"]
    conversation = state.get("conversation", [])
    background_context = state.get("background_context", "")
    
    sys_msg = SystemMessage(content=(
        f"You are the Opponent Agent in a formal debate. You strongly oppose the topic: '{topic}'.\n"
        f"Recent Context:\n{background_context}\n\n"
        "Give a concise 2-3 sentence counter-argument AGAINST the topic or expose weaknesses in the Pro's latest point. "
        "Do NOT start your response with any label such as [PRO], [OPPONENT], or any other tag. "
        "Respond ONLY with your counter-argument."
    ))
    conv_summary = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in conversation
    )
    messages = [sys_msg, HumanMessage(content=f"Debate so far:\n{conv_summary}\n\nYour counter-argument:")]
    response = base_llm.invoke(messages)
    return {"conversation": [{"role": "opponent", "content": _strip_role_prefix(response.content)}]}

def run_fact_checker(state: dict) -> dict:
    conversation = state.get("conversation", [])
    background_context = state.get("background_context", "")
    debate_id = state.get("debate_id", "default")
    
    if not conversation:
        return {}
        
    # Get the last claim (usually from opponent, but we just check the last message)
    last_msg = conversation[-1]["content"]
    
    # Query ChromaDB (Local Knowledge)
    facts = query_knowledge_base(last_msg, debate_id)
    
    # We combine local facts with recent web context
    all_facts = f"Database Facts:\\n{facts}\\n\\nRecent Web Context:\\n{background_context}"
    
    sys_msg = SystemMessage(content="You are a strict Fact Checker. Review the last claim against the provided facts. Output 'True', 'False', or 'Partially True' followed by a 1-sentence explanation based ONLY on the facts.")
    human_msg = HumanMessage(content=f"Claim: {last_msg}\\n\\nFacts:\\n{all_facts}")
    
    response = strict_llm.invoke([sys_msg, human_msg])
    
    return {"fact_checking_results": [{"claim": last_msg, "fact_check": response.content}],
            "conversation": [{"role": "fact_checker", "content": response.content}]}

def run_verdict_agent(state: dict) -> dict:
    topic = state["topic"]
    conversation = state.get("conversation", [])
    
    conv_text = "\\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in conversation])

    sys_msg = SystemMessage(content=f"""
You are the Verdict Agent for a formal debate on: '{topic}'.

Return STRICT JSON only. No markdown. No prose outside JSON.

Scoring rubric (use these exact criterion keys and point caps):
- argument_quality: 0-25
- evidence_use: 0-25
- rebuttal_effectiveness: 0-20
- factual_accuracy: 0-20
- clarity: 0-10

Required output schema:
{{
    "scores": {{
        "pro": {{"argument_quality":0,"evidence_use":0,"rebuttal_effectiveness":0,"factual_accuracy":0,"clarity":0,"total":0}},
        "opponent": {{"argument_quality":0,"evidence_use":0,"rebuttal_effectiveness":0,"factual_accuracy":0,"clarity":0,"total":0}}
    }},
    "winner": "pro|opponent|tie",
    "rationale": "1-2 sentences",
    "confidence": 0,
    "key_errors": {{"pro": [], "opponent": []}},
    "summary": "2-4 sentences"
}}

Rules:
1) total must equal the sum of that side's criteria before penalties.
2) Prefer concise, evidence-grounded judgments.
3) Use the fact checker turns as high-priority evidence when assigning factual_accuracy.
""".strip())
    human_msg = HumanMessage(content=f"Debate Transcript:\\n{conv_text}")
    
    response = strict_llm.invoke([sys_msg, human_msg])

    raw_payload = _extract_json_object(response.content)
    verdict_data = _normalize_verdict_payload(raw_payload)
    verdict_data = _apply_penalties(verdict_data, conversation)

    verdict_text = _format_verdict_summary(verdict_data)

    return {
        "verdict": verdict_text,
        "verdict_data": verdict_data,
        "conversation": [{"role": "verdict", "content": json.dumps(verdict_data, ensure_ascii=True)}],
    }


async def _run_node_in_executor(node_fn, state: dict) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(NODE_EXECUTOR, node_fn, state)


async def arun_moderator(state: dict) -> dict:
    return await _run_node_in_executor(run_moderator, state)


async def arun_researcher(state: dict) -> dict:
    return await _run_node_in_executor(run_researcher, state)


async def arun_pro_agent(state: dict) -> dict:
    return await _run_node_in_executor(run_pro_agent, state)


async def arun_opponent_agent(state: dict) -> dict:
    return await _run_node_in_executor(run_opponent_agent, state)


async def arun_fact_checker(state: dict) -> dict:
    return await _run_node_in_executor(run_fact_checker, state)


async def arun_verdict_agent(state: dict) -> dict:
    return await _run_node_in_executor(run_verdict_agent, state)
