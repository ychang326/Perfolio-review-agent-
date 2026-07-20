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

class RiskAgentNode:
    """
    Risk specialist: position-level risk proxies and diagnosis.
    Receives context from HoldingsAgent when is_risk_workflow is set.
    """
    def __init__(self):
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
        load_dotenv(dotenv_path)

        self.llm = ChatOpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model=os.getenv("MODEL", "qwen-plus"),
            base_url=os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            temperature=0.1, 
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
        target_tools = ["get_portfolio_holdings", "analyze_position_risk"]
        tools = [t for t in all_tools if t.name in target_tools]
        
        system_prompt = f"""You are a professional wealth-management 【Risk Agent】.
You take over after HoldingsAgent when a risk review is required.

Tools:
- get_portfolio_holdings — list positions (obtain real position_id first).
- analyze_position_risk — risk proxies for one position_id.
  metrics_7d_avg.volatility_proxy_pct / weight_pct / beta_proxy
  diagnosis ∈ RISK_NORMAL | RISK_WATCH | RISK_ELEVATED

Workflow (do this without asking the user for permission):
1. Read conversation context for holdings / position_id values.
2. If missing, call get_portfolio_holdings.
3. Prefer Open positions with the highest weight_pct. Call analyze_position_risk for the top 1–2 names (at least the largest weight).
4. Summarize concentration / volatility using tool numbers. State each diagnosis clearly.
5. No buy/sell advice. Never invent metrics. Never expose internal tool failures.

user_id is system-injected; pass placeholder "auto" if needed.
"""
        inner_agent = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_prompt
        )
        
        print("💡 [RiskAgent] Analyzing position risk metrics...")
        
        result = await inner_agent.ainvoke(
            {"messages": state["messages"]}, 
            config=config
        )
        
        final_message = result["messages"][-1]
        return {"messages": [final_message], "next_agent": ""}

# Backward-compatible alias
FinOpsAgentNode = RiskAgentNode
