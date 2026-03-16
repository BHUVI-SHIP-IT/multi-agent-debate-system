from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from database import query_knowledge_base
import os
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))

# We'll use llama3 as the default local model
# Ensure you have it pulled locally: ollama run llama3.2
MODEL = "llama3.2"
base_llm = ChatOllama(model=MODEL, temperature=0.7)
strict_llm = ChatOllama(model=MODEL, temperature=0.1)

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
    
    try:
        # Perform a web search to gather recent news and context
        search_result = tavily_client.search(query=topic, search_depth="basic", max_results=3)
        context_snippets = [f"- {res['title']}: {res['content']}" for res in search_result.get("results", [])]
        background_context = "\\n".join(context_snippets)
        if not background_context:
            background_context = "No recent web results found."
    except Exception as e:
        background_context = f"Failed to retrieve web search context: {str(e)}"
        search_result = {}

    return {
        "search_queries": [topic],
        "background_context": background_context,
        "conversation": [{"role": "researcher", "content": f"Gathered recent context for the debate:\\n{background_context}"}]
    }

def run_pro_agent(state: dict) -> dict:
    topic = state["topic"]
    conversation = state.get("conversation", [])
    background_context = state.get("background_context", "")
    
    sys_msg = SystemMessage(content=f"You are the Pro Agent. You strongly support the topic: '{topic}'.\\nRecent Context:\\n{background_context}\\nProvide a concise, 2-3 sentence argument supporting your stance using the recent context if applicable. Do not ramble.")
    messages = [sys_msg]
    for msg in conversation:
        role = "user" if msg["role"] != "pro" else "assistant"
        content = f"[{msg['role'].upper()}] {msg['content']}"
        messages.append(HumanMessage(content=content) if role == "user" else AIMessage(content=content))
        
    response = base_llm.invoke(messages)
    return {"conversation": [{"role": "pro", "content": response.content}]}

def run_opponent_agent(state: dict) -> dict:
    topic = state["topic"]
    conversation = state.get("conversation", [])
    background_context = state.get("background_context", "")
    
    sys_msg = SystemMessage(content=f"You are the Opponent Agent. You strongly oppose the topic: '{topic}'.\\nRecent Context:\\n{background_context}\\nProvide a concise, 2-3 sentence counter-argument or expose weaknesses in the Pro argument using the recent context if applicable. Do not ramble.")
    messages = [sys_msg]
    for msg in conversation:
        role = "user" if msg["role"] != "opponent" else "assistant"
        content = f"[{msg['role'].upper()}] {msg['content']}"
        messages.append(HumanMessage(content=content) if role == "user" else AIMessage(content=content))
        
    response = base_llm.invoke(messages)
    return {"conversation": [{"role": "opponent", "content": response.content}]}

def run_fact_checker(state: dict) -> dict:
    conversation = state.get("conversation", [])
    background_context = state.get("background_context", "")
    
    if not conversation:
        return {}
        
    # Get the last claim (usually from opponent, but we just check the last message)
    last_msg = conversation[-1]["content"]
    
    # Query ChromaDB (Local Knowledge)
    facts = query_knowledge_base(last_msg)
    
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
    
    sys_msg = SystemMessage(content=f"You are the Verdict Agent. Analyze the debate on '{topic}' and provide a final verdict summarizing the best points and deciding the outcome in 3-4 sentences.")
    human_msg = HumanMessage(content=f"Debate Transcript:\\n{conv_text}")
    
    response = base_llm.invoke([sys_msg, human_msg])
    
    return {"verdict": response.content,
            "conversation": [{"role": "verdict", "content": response.content}]}
