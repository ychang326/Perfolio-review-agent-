import os
import sys
from pathlib import Path
# Caller (main.py) is expected to set sys.path.

import asyncio
from typing import Literal

from langgraph.graph import StateGraph, START, END
from core.workflow.state import AgentState
from agents.orchestrator import OrchestratorAgent
from agents.product_agent import KnowledgeAgentNode
from agents.billing_agent import HoldingsAgentNode
from agents.promotion_agent import AttributionAgentNode
from agents.recommendation_agent import PerformanceAgent
from agents.finops_agent import RiskAgentNode

class AgentGraphManager:
    """
    Assembles the LangGraph multi-agent graph.
    Supports holdings → risk handoff via metadata.is_risk_workflow.
    """
    def __init__(self):
        self.orchestrator = OrchestratorAgent()
        self.knowledge_node = KnowledgeAgentNode()
        self.holdings_node = HoldingsAgentNode()
        self.attribution_node = AttributionAgentNode()
        self.performance_node = PerformanceAgent()
        self.risk_node = RiskAgentNode()

    def _route_condition(self, state: AgentState) -> str:
        """Route to the specialist chosen by the orchestrator."""
        return state.get("next_agent", "knowledge_agent")

    def _holdings_post_condition(self, state: AgentState) -> str:
        """
        After holdings_agent:
        if risk workflow → risk_agent; else END.
        """
        if state.get("metadata", {}).get("is_risk_workflow"):
            return "risk_agent"
        return END

    def build_graph(self) -> StateGraph:
        """Build the state graph."""
        builder = StateGraph(AgentState)

        builder.add_node("orchestrator", self.orchestrator.route)
        builder.add_node("knowledge_agent", self.knowledge_node)
        builder.add_node("holdings_agent", self.holdings_node)
        builder.add_node("attribution_agent", self.attribution_node)
        builder.add_node("performance_agent", self.performance_node)
        builder.add_node("risk_agent", self.risk_node)

        builder.add_edge(START, "orchestrator")

        builder.add_conditional_edges(
            "orchestrator",
            self._route_condition,
            {
                "knowledge_agent": "knowledge_agent",
                "holdings_agent": "holdings_agent",
                "attribution_agent": "attribution_agent",
                "performance_agent": "performance_agent",
            }
        )

        builder.add_conditional_edges(
            "holdings_agent",
            self._holdings_post_condition,
            {
                "risk_agent": "risk_agent",
                END: END
            }
        )

        builder.add_edge("knowledge_agent", END)
        builder.add_edge("attribution_agent", END)
        builder.add_edge("performance_agent", END)
        builder.add_edge("risk_agent", END)

        return builder.compile()

async def test_graph():
    manager = AgentGraphManager()
    graph = manager.build_graph()

    print("Starting WM Portfolio multi-agent system...")
    print("=" * 60)
    
    state: AgentState = {
        "messages": [("user", "What is asset allocation?")],
        "user_id": "user_1001",
        "session_id": "test_session_1",
        "memory_context": "",
        "next_agent": "",
        "metadata": {}
    }
    print(f"User: {state['messages'][0][1]}")
    
    result = await graph.ainvoke(state)
    print(f"AI: {result['messages'][-1].content}\n")

    state["messages"] = result["messages"]
    state["messages"].append(("user", "Show my current holdings."))
    
    print(f"User: {state['messages'][-1][1]}")
    result = await graph.ainvoke(state)
    print(f"AI: {result['messages'][-1].content}\n")

if __name__ == "__main__":
    asyncio.run(test_graph())
