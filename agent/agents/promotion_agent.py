"""
 * 小滴课堂,愿景：让技术不再难学
 * @Remark 有问题联系我【xdclass68】
 * 源码-笔记-技术交流群,官网 https://xdclass.net
"""
import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from typing import Dict, Any

from core.workflow.state import AgentState
from agents.billing_agent import UserIdInjector

class AttributionAgentNode:
    """
    Attribution specialist: drivers of portfolio change / contribution narrative.
    Image-generation tool removed.
    """
    def __init__(self):
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
        load_dotenv(dotenv_path)

        self.llm = ChatOpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model=os.getenv("MODEL", "qwen-plus"),
            base_url=os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            temperature=0.3,
        )
        
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'mcp_servers.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            self.servers_config = json.load(f)
        import sys
        agent_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for _srv in self.servers_config.get("mcpServers", {}).values():
            _srv["cwd"] = agent_root
            if _srv.get("command") in ("python", "python3"):
                _srv["command"] = sys.executable

    async def _ensure_tools(self):
        pass

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        config = {"configurable": {"user_id": state.get("user_id", "unknown")}}
        
        client = MultiServerMCPClient(
            connections=self.servers_config.get("mcpServers", {}),
            tool_interceptors=[UserIdInjector()]
        )
        all_tools = await client.get_tools()
        target_tools = [
            "list_instruments",
            "search_instruments",
            "get_instrument_factsheet",
            "get_portfolio_transactions",
            "get_portfolio_holdings",
        ]
        tools = [t for t in all_tools if t.name in target_tools]

        memory_context = state.get("memory_context", "")
        
        system_prompt = f"""You are a professional wealth-management 【Attribution Agent】.
You explain what drove recent portfolio P&L / changes using holdings, transactions, and factsheets.

Tools:
- get_portfolio_holdings — current positions / weights.
- get_portfolio_transactions — trades that explain activity effects.
- search_instruments — resolve a name/ticker to instrument_id.
- get_instrument_factsheet — disclosure / risk context for that instrument.
- list_instruments — catalog overview if the user is exploring broadly.

Workflow:
1. If the user asks why the portfolio moved, fetch holdings and recent transactions.
2. Attribute contribution qualitatively from tool amounts/weights (largest absolute impacts, largest weights).
3. For a named instrument, resolve instrument_id then pull the factsheet.
4. No buy/sell advice. No fabricated Brinson numbers unless present in tool output.
5. user_id is injected; pass "auto" if needed.

[Memory context]:
{memory_context if memory_context else "No prior memory."}
"""
        inner_agent = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_prompt
        )
        
        print("📢 [AttributionAgent] Building attribution narrative...")
        
        result = await inner_agent.ainvoke(
            {"messages": state["messages"]}, 
            config=config
        )
        
        final_message = result["messages"][-1]
        return {"messages": [final_message]}

# Backward-compatible alias
PromotionAgentNode = AttributionAgentNode
