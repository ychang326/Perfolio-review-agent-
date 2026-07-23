"""Holdings Agent — portfolio positions, weights, allocation."""
import os
import sys
import json
import asyncio
from typing import Dict, Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from core.workflow.state import AgentState
from agents.user_id_injector import UserIdInjector


class HoldingsAgentNode:
    """Holdings specialist: client positions, weights, allocation."""

    def __init__(self):
        agent_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        load_dotenv(os.path.join(agent_root, ".env"))

        self.llm = ChatOpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model=os.getenv("MODEL", "qwen-plus"),
            base_url=os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            temperature=0.1,
        )

        config_path = os.path.join(agent_root, "config", "mcp_servers.json")
        with open(config_path, "r", encoding="utf-8") as f:
            self.servers_config = json.load(f)
        for _srv in self.servers_config.get("mcpServers", {}).values():
            _srv["cwd"] = agent_root
            if _srv.get("command") in ("python", "python3"):
                _srv["command"] = sys.executable

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        config = {"configurable": {"user_id": state.get("user_id", "unknown")}}
        memory_context = state.get("memory_context", "")
        system_prompt = f"""You are a professional wealth-management 【Holdings Agent】.
You query the client's portfolio positions and related transactions via tools.

Tools:
- get_portfolio_holdings — current positions (position_id, instrument, asset_class, sector, quantity, market_value, weight_pct, status).
- get_portfolio_transactions — recent trades / ledger lines (txn_id, side, quantity, amount, trade_date).

Rules:
- For "what do I hold / allocation / weights / positions", call get_portfolio_holdings.
- For "recent trades / transactions / ledger", call get_portfolio_transactions.
- user_id is injected by the system; pass a placeholder like "auto" if required.
- Never reveal raw user_id. Only the logged-in client's data is allowed.
- Never invent positions, weights, or amounts. Use tool results only.
- Do not say tools are broken; if a call fails, give a neutral retry message.
- Do not give buy/sell advice or return guarantees. Facts only.

[Memory context]:
{memory_context if memory_context else "No prior memory."}
"""
        print("💡 [HoldingsAgent] Handling holdings / allocation query...")

        client = MultiServerMCPClient(
            connections=self.servers_config.get("mcpServers", {}),
            tool_interceptors=[UserIdInjector()],
        )
        all_tools = await client.get_tools()
        allowed_tool_names = {"get_portfolio_holdings", "get_portfolio_transactions"}
        tools = [tool for tool in all_tools if tool.name in allowed_tool_names]

        inner_agent = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_prompt,
        )
        result = await inner_agent.ainvoke({"messages": state["messages"]}, config=config)
        return {"messages": [result["messages"][-1]]}


async def test_holdings_agent():
    print("🤖 HoldingsAgent test entry — wire MCP + graph for full e2e.")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_holdings_agent())
