"""Performance Agent — portfolio P&L and performance narrative."""
import os
import sys
import json
from typing import Dict, Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from core.workflow.state import AgentState
from agents.user_id_injector import UserIdInjector
from tools.vector_tool import query_vector_db


class PerformanceAgentNode:
    """Performance / P&L specialist."""

    def __init__(self):
        agent_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        load_dotenv(os.path.join(agent_root, ".env"))

        self.llm = ChatOpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model=os.getenv("MODEL", "qwen-plus"),
            base_url=os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            temperature=0.3,
        )

        config_path = os.path.join(agent_root, "config", "mcp_servers.json")
        with open(config_path, "r", encoding="utf-8") as f:
            self.servers_config = json.load(f)
        for _srv in self.servers_config.get("mcpServers", {}).values():
            _srv["cwd"] = agent_root
            if _srv.get("command") in ("python", "python3"):
                _srv["command"] = sys.executable

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        memory_context = state.get("memory_context", "")
        config = {"configurable": {"user_id": state.get("user_id", "unknown")}}

        client = MultiServerMCPClient(
            connections=self.servers_config.get("mcpServers", {}),
            tool_interceptors=[UserIdInjector()],
        )
        all_tools = await client.get_tools()
        target_tools = [
            "list_instruments",
            "search_instruments",
            "get_instrument_factsheet",
            "get_portfolio_transactions",
            "get_portfolio_holdings",
        ]
        mcp_tools = [t for t in all_tools if t.name in target_tools]
        tools = [query_vector_db] + mcp_tools

        system_prompt = f"""You are a professional wealth-management 【Performance Agent】.
You explain portfolio P&L and performance using tools only.

Tools:
- get_portfolio_transactions — trades / ledger lines (side, quantity, amount, trade_date, status).
- get_portfolio_holdings — current market values and weights for context.
- list_instruments / search_instruments / get_instrument_factsheet — instrument context when needed.
- query_vector_db — optional methodology notes from docs.

Rules:
- For day/period P&L or recent performance, call get_portfolio_transactions first (and holdings if useful).
- State clearly that figures come from ledger / holdings; do not invent TWR/XIRR if not in tool output.
- No buy/sell recommendations. No return guarantees.
- Never fabricate amounts. Cite tool-backed numbers only.
- user_id is injected; use placeholder "auto" if needed.

[Memory context]:
{memory_context if memory_context else "No prior memory."}
"""
        inner_agent = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_prompt,
        )
        print("🔍 [PerformanceAgent] Computing performance / P&L narrative...")
        result = await inner_agent.ainvoke({"messages": state["messages"]}, config=config)
        return {"messages": [result["messages"][-1]]}
