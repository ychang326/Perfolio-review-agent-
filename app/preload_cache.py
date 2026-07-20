import asyncio
import sys
import os

# Ensure app modules import correctly
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

from infra.cache import semantic_cache

# Preset WM FAQ for L1 semantic cache warm-up
PRESET_QA = [
    {
        "query": "What is asset allocation?",
        "response": (
            "### Asset Allocation\n\n"
            "Asset allocation is how a portfolio is split across asset classes "
            "(e.g. Equity, Fixed Income, Fund, Cash).\n\n"
            "- **Purpose**: balance return potential vs risk and liquidity needs.\n"
            "- **In this assistant**: ask *Show my current holdings and weights* "
            "to see your personal allocation from live holdings data.\n\n"
            "> Not investment advice. Figures for your account come from portfolio tools only."
        ),
    },
    {
        "query": "Explain concentration risk in a portfolio.",
        "response": (
            "### Concentration Risk\n\n"
            "Concentration risk rises when a large share of portfolio value sits in "
            "a single name, sector, or asset class.\n\n"
            "- **Single-name**: one instrument dominates weight (e.g. >25%).\n"
            "- **Sector**: many holdings share the same industry exposure.\n"
            "- **In this assistant**: ask *Is my portfolio too concentrated? Review risk.* "
            "to run a risk review on your positions.\n\n"
            "> Educational only. Your live flags come from risk tools, not this FAQ."
        ),
    },
    {
        "query": "What is the difference between TWR and XIRR?",
        "response": (
            "### TWR vs XIRR (MWR)\n\n"
            "- **TWR (Time-Weighted Return)**: measures investment performance "
            "removing the effect of cash deposits/withdrawals.\n"
            "- **XIRR / MWR (Money-Weighted Return)**: reflects the client's actual "
            "timing of cash flows into and out of the portfolio.\n\n"
            "When both exist, always check which `method` the performance tool used. "
            "This assistant will not invent TWR/XIRR if the tool output does not include them."
        ),
    },
    {
        "query": "What does day P&L mean?",
        "response": (
            "### Day P&L\n\n"
            "Day P&L is the mark-to-market profit or loss for the current trading day "
            "(absolute amount and/or percent).\n\n"
            "- Ask *How is my portfolio P&L looking recently?* for ledger-based recent activity.\n"
            "- Ask *Show my recent portfolio transactions* for Buy/Sell/Dividend/Fee lines.\n\n"
            "> Past performance is not indicative of future results."
        ),
    },
]

async def preload_cache():
    print("Starting L1 semantic cache warm-up (WM FAQ)...")
    await semantic_cache.initialize()
    
    for item in PRESET_QA:
        query = item["query"]
        response = item["response"]
        print(f"Inject cache -> Query: '{query}'")
        
        await semantic_cache.set_cache(query, response)
        
    print("Cache warm-up complete.")

if __name__ == "__main__":
    asyncio.run(preload_cache())
