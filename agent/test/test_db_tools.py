"""Smoke test for WM portfolio MCP tools (requires DB + seeded mock data)."""
from mcp_servers.cloud_platform_server import (
    get_portfolio_transactions,
    get_portfolio_holdings,
    analyze_position_risk,
    search_instruments,
    get_instrument_factsheet,
)


def run():
    print("--- get_portfolio_transactions(user_1001) ---")
    print(get_portfolio_transactions(user_id="user_1001", limit=10))

    print("\n--- get_portfolio_holdings(user_1002) ---")
    print(get_portfolio_holdings(user_id="user_1002"))

    print("\n--- get_portfolio_holdings(user_9999) ---")
    print(get_portfolio_holdings(user_id="user_9999"))

    print("\n--- analyze_position_risk(pos-user1001-aapl) ---")
    print(analyze_position_risk(position_id="pos-user1001-aapl", user_id="user_1001"))

    print("\n--- search_instruments('AAPL') ---")
    print(search_instruments(keyword="AAPL"))

    print("\n--- get_instrument_factsheet('EQ_AAPL') ---")
    print(get_instrument_factsheet(instrument_id="EQ_AAPL", user_id="user_1001"))


if __name__ == "__main__":
    run()
