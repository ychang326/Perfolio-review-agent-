"""
 * 小滴课堂,愿景：让技术不再难学
 * @Remark 有问题联系我【xdclass68】
 * 源码-笔记-技术交流群,官网 https://xdclass.net
"""
import os
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from core.workflow.state import AgentState

class OrchestratorAgent:
    """
    Central router node (Orchestrator).
    Classifies user intent and dispatches to a specialist agent.
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

    async def route(self, state: AgentState) -> Dict[str, Any]:
        """
        Decide the next specialist agent from the latest user message.
        """
        messages = state.get("messages", [])
        if not messages:
            last_message = ""
        else:
            last_msg_obj = messages[-1]
            if isinstance(last_msg_obj, tuple):
                last_message = last_msg_obj[1]
            elif hasattr(last_msg_obj, "content"):
                last_message = last_msg_obj.content
            else:
                last_message = str(last_msg_obj)
        memory_context = state.get("memory_context", "")

        system_prompt = f"""You are the orchestrator for a wealth-management portfolio assistant.
Your only job is to route the user's question to exactly one specialist agent.

Available agents:
1. "knowledge_agent" — product terms, disclosures, policy / FAQ style questions that are NOT about the client's own holdings numbers.
2. "holdings_agent" — the client's positions, weights, asset allocation, what they currently hold.
3. "attribution_agent" — why the portfolio moved, contribution of names/sectors, recent transaction-driven changes.
4. "performance_agent" — P&L, returns, day P&L, period performance, XIRR/CAGR-style performance questions.
5. "risk_agent_trigger" — risk, volatility, concentration, stress, "is my portfolio too risky / too concentrated".

Routing rules (high priority):
- Questions about "my holdings / weights / allocation / what do I own" → holdings_agent.
- Questions about "P&L / return / how much did I make / YTD performance" → performance_agent.
- Questions about "why did it drop / contribution / what drove performance" → attribution_agent.
- Questions about "risk / volatility / concentration / stress" → risk_agent_trigger.
- General education / factsheet / disclosure without personal portfolio numbers → knowledge_agent.

[Memory context]:
{memory_context}

Output ONLY one of: knowledge_agent, holdings_agent, attribution_agent, performance_agent, risk_agent_trigger
No other text. If unsure, default to knowledge_agent.
"""

        response = await self.llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=last_message)
        ])
        
        decision = response.content.strip().lower()
        if "risk" in decision:
            next_node = "holdings_agent"
            state["metadata"]["is_risk_workflow"] = True
            print("🧭 [Orchestrator] Risk intent → risk workflow (step 1: holdings_agent)")
        elif "holdings" in decision:
            next_node = "holdings_agent"
            state["metadata"]["is_risk_workflow"] = False
            print("🧭 [Orchestrator] Routed to: holdings_agent")
        elif "attribution" in decision:
            next_node = "attribution_agent"
            print("🧭 [Orchestrator] Routed to: attribution_agent")
        elif "performance" in decision:
            next_node = "performance_agent"
            print("🧭 [Orchestrator] Routed to: performance_agent")
        else:
            next_node = "knowledge_agent"
            print("🧭 [Orchestrator] Routed to: knowledge_agent")
            
        return {"next_agent": next_node, "metadata": state.get("metadata", {})}
