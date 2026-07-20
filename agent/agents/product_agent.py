"""
 * 小滴课堂,愿景：让技术不再难学
 * @Remark 有问题联系我【xdclass68】
 * 源码-笔记-技术交流群,官网 https://xdclass.net
"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import create_react_agent

from tools.vector_tool import query_vector_db
from tools.graph_tool import query_knowledge_graph
from core.workflow.state import AgentState
from typing import Dict, Any

class KnowledgeAgentNode:
    """
    Knowledge specialist: disclosures, product concepts, policy Q&A via RAG/KG.
    Tool wiring unchanged (query_vector_db / query_knowledge_graph).
    """
    def __init__(self):
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        load_dotenv(dotenv_path)

        self.llm = ChatOpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model=os.getenv("MODEL", "qwen-plus"),
            base_url=os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            temperature=0.1, 
        )
        self.tools = [query_vector_db, query_knowledge_graph]

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        memory_context = state.get("memory_context", "")
        system_prompt = f"""You are a professional wealth-management 【Knowledge Agent】.
You answer educational / disclosure questions about investment products, risks, and policies.
You do NOT query the client's personal holdings numbers (that is HoldingsAgent).

Tools:
1. query_vector_db — semantic search over documents (concepts, procedures, policy text).
2. query_knowledge_graph — structured relations / attributes when available.

Rules:
- Prefer tools for facts; do not hallucinate regulations or product terms.
- If structured limits/relations are needed, try query_knowledge_graph first; on timeout/failure, fall back to query_vector_db.
- Never give personalized buy/sell advice or guaranteed returns.
- Cite only sources that actually appeared in tool output.
- End with sources actually used, e.g.:
  Sources:
  - Vector retrieval: xxx.md

[Memory context]:
{memory_context if memory_context else "No prior memory."}
"""
        inner_agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt
        )
        
        print("💡 [KnowledgeAgent] Handling knowledge / disclosure query...")
        
        result = await inner_agent.ainvoke({"messages": state["messages"]})
        final_message = result["messages"][-1]
        return {"messages": [final_message]}

# Backward-compatible alias
ProductAgentNode = KnowledgeAgentNode


def get_product_agent():
    """Kept for legacy test entrypoints."""
    pass

if __name__ == "__main__":
    agent = get_product_agent()
    
    print("🤖 KnowledgeAgent started! (type 'quit' / 'exit' to stop)")
    print("=" * 50)

    config = {"configurable": {"thread_id": "test_thread_1"}}

    while True:
        user_input = input("\n👤 User: ")
        if user_input.lower() in ['quit', 'exit']:
            break
            
        if not user_input.strip():
            continue

        print("\n🤖 Thinking...")
        
        try:
            for event in agent.stream({"messages": [("user", user_input)]}, config=config, stream_mode="values"):
                last_message = event["messages"][-1]
                if getattr(last_message, "tool_calls", None):
                    for tc in last_message.tool_calls:
                        print(f"   [Tool Call] {tc['name']} (args: {tc['args']})")
            
            final_message = event["messages"][-1].content
            print(f"\n💡 KnowledgeAgent: {final_message}")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
