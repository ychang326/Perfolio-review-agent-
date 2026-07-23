import os
import pymysql
import json
import sys
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# ==============================================================================
# Environment
# ==============================================================================
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path)

mcp = FastMCP("WealthPortfolioMCPServer")


def get_db_connection():
    """Get MySQL connection. Production should use a pool."""
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "YOUR_MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "YOUR_MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE", "cloud_platform"),
        cursorclass=pymysql.cursors.DictCursor,
    )


def _float_fields(row: dict, keys: list[str]) -> dict:
    for k in keys:
        if k in row and row[k] is not None:
            row[k] = float(row[k])
    return row


# ==============================================================================
# Instrument master (in-memory catalog for search / factsheet)
# ==============================================================================
INSTRUMENT_CATALOG = {
    "EQ_AAPL": {
        "name": "Apple Inc.",
        "keywords": ["aapl", "apple", "equity", "tech", "stock"],
        "asset_class": "Equity",
        "sector": "Technology",
        "currency": "USD",
    },
    "EQ_MSFT": {
        "name": "Microsoft Corp.",
        "keywords": ["msft", "microsoft", "equity", "tech", "stock"],
        "asset_class": "Equity",
        "sector": "Technology",
        "currency": "USD",
    },
    "EQ_JPM": {
        "name": "JPMorgan Chase & Co.",
        "keywords": ["jpm", "jpmorgan", "equity", "financials", "bank"],
        "asset_class": "Equity",
        "sector": "Financials",
        "currency": "USD",
    },
    "BD_UST10Y": {
        "name": "US Treasury 10Y Note ETF",
        "keywords": ["ust", "treasury", "bond", "fixed income", "duration"],
        "asset_class": "Fixed Income",
        "sector": "Government",
        "currency": "USD",
    },
    "MF_SP500": {
        "name": "S&P 500 Index Fund",
        "keywords": ["sp500", "index", "fund", "mutual fund", "equity"],
        "asset_class": "Fund",
        "sector": "Broad Market",
        "currency": "USD",
    },
    "CASH_USD": {
        "name": "USD Cash",
        "keywords": ["cash", "usd", "money market", "liquidity"],
        "asset_class": "Cash",
        "sector": "Cash",
        "currency": "USD",
    },
}


# ==============================================================================
# MCP Tools — WM portfolio domain
# ==============================================================================

@mcp.tool()
def list_instruments() -> str:
    """
    List instruments available in the research / factsheet catalog
    (not the client's live holdings). Use when the user asks which
    instruments can be looked up.
    """
    items = []
    for instrument_id, info in INSTRUMENT_CATALOG.items():
        items.append({
            "instrument_id": instrument_id,
            "name": info["name"],
            "asset_class": info["asset_class"],
            "sector": info["sector"],
            "currency": info["currency"],
        })

    return json.dumps({
        "status": "success",
        "message": "Instruments available in the catalog:",
        "data": items,
    }, ensure_ascii=False)


@mcp.tool()
def search_instruments(keyword: str) -> str:
    """
    Fuzzy-search instruments by ticker, name, asset class, or sector.

    Args:
        keyword: Natural-language or ticker keyword, e.g. "AAPL", "treasury", "tech".
    """
    results = []
    kw = keyword.lower()

    for instrument_id, info in INSTRUMENT_CATALOG.items():
        haystacks = [
            info["name"].lower(),
            info["asset_class"].lower(),
            info["sector"].lower(),
            instrument_id.lower(),
            *info["keywords"],
        ]
        if any(kw in h for h in haystacks):
            results.append({
                "instrument_id": instrument_id,
                "name": info["name"],
                "asset_class": info["asset_class"],
                "sector": info["sector"],
                "currency": info["currency"],
            })

    if not results:
        return json.dumps({
            "status": "not_found",
            "message": f"No instrument matching '{keyword}'.",
            "recommendation": {
                "instrument_id": "MF_SP500",
                "name": "S&P 500 Index Fund",
            },
        }, ensure_ascii=False)

    return json.dumps({"status": "success", "data": results}, ensure_ascii=False)


@mcp.tool()
def get_instrument_factsheet(instrument_id: str, user_id: str = "") -> str:
    """
    Return disclosure / factsheet summary for an instrument.
    Prefer calling search_instruments first to resolve instrument_id.

    Args:
        instrument_id: Canonical id, e.g. "EQ_AAPL", "BD_UST10Y".
        user_id: [system-injected] client id for audit trail.
    """
    factsheets = {
        "EQ_AAPL": {
            "title": "Apple Inc. (AAPL) — Equity Factsheet",
            "summary": "Large-cap US technology equity. Key risks: valuation, single-name concentration, FX for non-USD base.",
            "risk_disclosure": "Past performance is not indicative of future results. Not investment advice.",
            "asset_class": "Equity",
            "benchmark": "S&P 500",
        },
        "EQ_MSFT": {
            "title": "Microsoft Corp. (MSFT) — Equity Factsheet",
            "summary": "Large-cap US technology equity with cloud/software exposure.",
            "risk_disclosure": "Past performance is not indicative of future results. Not investment advice.",
            "asset_class": "Equity",
            "benchmark": "S&P 500",
        },
        "EQ_JPM": {
            "title": "JPMorgan Chase (JPM) — Equity Factsheet",
            "summary": "US financials equity. Sensitive to rates and credit cycle.",
            "risk_disclosure": "Past performance is not indicative of future results. Not investment advice.",
            "asset_class": "Equity",
            "benchmark": "S&P 500 Financials",
        },
        "BD_UST10Y": {
            "title": "US Treasury 10Y Note ETF — Fixed Income Factsheet",
            "summary": "Duration-sensitive government bond exposure. Rate-up scenarios may reduce NAV.",
            "risk_disclosure": "Bond prices move inversely with yields. Not investment advice.",
            "asset_class": "Fixed Income",
            "benchmark": "Bloomberg US Treasury 7-10Y",
        },
        "MF_SP500": {
            "title": "S&P 500 Index Fund — Fund Factsheet",
            "summary": "Broad US large-cap equity index exposure. Market beta approximately 1.",
            "risk_disclosure": "Index funds can lose value. Not investment advice.",
            "asset_class": "Fund",
            "benchmark": "S&P 500",
        },
        "CASH_USD": {
            "title": "USD Cash — Liquidity Sleeve",
            "summary": "Cash / money-market style liquidity buffer.",
            "risk_disclosure": "Cash may earn low real yield. Not investment advice.",
            "asset_class": "Cash",
            "benchmark": "SOFR",
        },
    }

    sheet = factsheets.get(instrument_id)
    if not sheet:
        return json.dumps({
            "status": "not_found",
            "message": f"No factsheet for instrument_id '{instrument_id}'.",
            "recommendation": {"instrument_id": "MF_SP500", "name": "S&P 500 Index Fund"},
        }, ensure_ascii=False)

    return json.dumps({
        "status": "success",
        "data": {
            "instrument_id": instrument_id,
            "title": sheet["title"],
            "summary": sheet["summary"],
            "risk_disclosure": sheet["risk_disclosure"],
            "asset_class": sheet["asset_class"],
            "benchmark": sheet["benchmark"],
            "factsheet_url": (
                f"https://wm.internal/factsheets/{instrument_id}?client={user_id}"
                if user_id else f"https://wm.internal/factsheets/{instrument_id}"
            ),
        },
    }, ensure_ascii=False)


@mcp.tool()
def get_portfolio_transactions(user_id: str, limit: int = 5) -> str:
    """
    Query the client's recent portfolio transactions / ledger activity.

    Args:
        user_id: [system-injected] client id. Must not be forged by the model.
        limit: Max rows to return (default 5).
    """
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
                SELECT
                    txn_id,
                    instrument_id,
                    instrument_name,
                    side,
                    quantity,
                    amount,
                    currency,
                    status,
                    DATE_FORMAT(trade_date, '%%Y-%%m-%%d %%H:%%i:%%s') AS trade_date
                FROM portfolio_transactions
                WHERE user_id = %s
                ORDER BY trade_date DESC
                LIMIT %s
            """
            cursor.execute(sql, (user_id, limit))
            results = cursor.fetchall()

            if not results:
                return json.dumps({
                    "status": "success",
                    "message": "This client currently has no transaction records.",
                }, ensure_ascii=False)

            for row in results:
                _float_fields(row, ["quantity", "amount"])

            return json.dumps({"status": "success", "data": results}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Database query failed: {str(e)}"}, ensure_ascii=False)
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()


@mcp.tool()
def get_portfolio_holdings(user_id: str, limit: int = 5) -> str:
    """
    Query the client's current portfolio holdings (positions, weights, asset class).

    Args:
        user_id: [system-injected] client id.
        limit: Max positions to return (default 5).
    """
    sql = """
        SELECT
            position_id,
            instrument_id,
            instrument_name,
            asset_class,
            sector,
            quantity,
            market_value,
            weight_pct,
            currency,
            status,
            DATE_FORMAT(as_of, '%%Y-%%m-%%d') AS as_of
        FROM portfolio_holdings
        WHERE user_id = %s
        ORDER BY weight_pct DESC
        LIMIT %s
    """

    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(sql, (user_id, limit))
            result = cursor.fetchall()

            if not result:
                return json.dumps({
                    "status": "success",
                    "message": "No holdings were found for this client.",
                }, ensure_ascii=False)

            for row in result:
                _float_fields(row, ["quantity", "market_value", "weight_pct"])

            return json.dumps({"status": "success", "data": result}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Database query failed: {str(e)}"}, ensure_ascii=False)
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()


@mcp.tool()
def analyze_position_risk(position_id: str, user_id: str = "") -> str:
    """
    Return recent risk metrics for one holding/position and a diagnosis flag.

    Args:
        position_id: Position id from get_portfolio_holdings, e.g. "pos-user1001-aapl".
        user_id: [system-injected] client id for authorization.
    """
    if not position_id:
        return json.dumps({"status": "error", "message": "position_id is required"}, ensure_ascii=False)

    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            auth_sql = """
                SELECT position_id, instrument_id, weight_pct
                FROM portfolio_holdings
                WHERE position_id = %s AND user_id = %s
                LIMIT 1
            """
            cursor.execute(auth_sql, (position_id, user_id))
            owned = cursor.fetchone()
            if not owned:
                return json.dumps({
                    "status": "error",
                    "message": "Position not found, or you are not authorized to view its risk metrics.",
                }, ensure_ascii=False)

            metrics_sql = """
                SELECT
                    ROUND(AVG(volatility_proxy_pct), 2) AS volatility_proxy_pct,
                    ROUND(AVG(weight_pct), 2) AS weight_pct,
                    ROUND(AVG(beta_proxy), 2) AS beta_proxy,
                    COUNT(*) AS days_count
                FROM position_risk_daily
                WHERE position_id = %s
                  AND user_id = %s
                  AND metric_date >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
            """
            cursor.execute(metrics_sql, (position_id, user_id))
            agg = cursor.fetchone()

            if not agg or not agg.get("days_count"):
                return json.dumps({
                    "status": "error",
                    "message": "No recent risk metrics found for this position. Please try again later.",
                }, ensure_ascii=False)

            vol = float(agg["volatility_proxy_pct"] or 0)
            weight = float(agg["weight_pct"] or 0)
            beta = float(agg["beta_proxy"] or 0)

            if weight >= 25 or vol >= 30:
                diagnosis = "RISK_ELEVATED"
            elif weight >= 15 or vol >= 20:
                diagnosis = "RISK_WATCH"
            else:
                diagnosis = "RISK_NORMAL"

            return json.dumps({
                "status": "success",
                "data": {
                    "position_id": position_id,
                    "instrument_id": owned["instrument_id"],
                    "owner_id": user_id,
                    "metrics_7d_avg": {
                        "volatility_proxy_pct": vol,
                        "weight_pct": weight,
                        "beta_proxy": beta,
                    },
                    "diagnosis": diagnosis,
                },
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Risk metrics query failed: {str(e)}"}, ensure_ascii=False)
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()


if __name__ == "__main__":
    sys.stderr.write("Starting Wealth Portfolio MCP Server (stdio mode)...\n")
    mcp.run()
