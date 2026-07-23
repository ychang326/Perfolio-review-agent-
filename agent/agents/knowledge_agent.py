"""Knowledge Agent — WM education, disclosures, policy Q&A via RAG/KG."""
import os
from typing import Dict, Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from tools.vector_tool import query_vector_db
from tools.graph_tool import query_knowledge_graph
from core.workflow.state import AgentState


class KnowledgeAgentNode:
    """Knowledge specialist: disclosures and concepts via RAG/KG."""

    def __init__(self):
        agent_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        load_dotenv(os.path.join(agent_root, ".env"))

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
            prompt=system_prompt,
        )
        print("💡 [KnowledgeAgent] Handling knowledge / disclosure query...")
        result = await inner_agent.ainvoke({"messages": state["messages"]})
        return {"messages": [result["messages"][-1]]}
