from langchain_ollama import ChatOllama

def main():
    print("Initializing ChatOllama...")
    llm = ChatOllama(model="llama3.2", temperature=0.7)
    print("Invoking...")
    response = llm.invoke("Hello! Respond with a single word.")
    print("Response:", response.content)

if __name__ == "__main__":
    main()
