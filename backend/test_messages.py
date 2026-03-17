from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

def test_messages():
    llm = ChatOllama(model="llama3.2")
    msgs = [
        SystemMessage(content="You are the PRO ARGUMENT agent. Make a strong argument."),
        AIMessage(content="[MODERATOR] The debate begins.")
    ]
    print("Calling invoke...", flush=True)
    res = llm.invoke(msgs)
    print("FINISHED!", flush=True)
    print(res.content)

if __name__ == "__main__":
    test_messages()
