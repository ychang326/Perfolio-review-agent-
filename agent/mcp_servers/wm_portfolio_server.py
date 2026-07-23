import os
import pymysql
import json
import sys
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from mcp_servers.instrument_store import get_instrument_store

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


def _milvus_error(exc: Exception) -> str:
    return json.dumps({
        "status": "error",
        "message": (
            f"Instrument Milvus store unavailable: {exc}. "
            "Set MILVUS_HOST / DASHSCOPE_API_KEY, then run: "
            "python -m test.ingest_instruments"
        ),
    }, ensure_ascii=False)


# ==============================================================================
# MCP Tools — WM portfolio domain
# ==============================================================================

@mcp.tool()
def list_instruments(limit: int = 50) -> str:
    """
    List instruments from the Milvus research catalog
    (not the client's live holdings). Use when the user asks which
    instruments can be looked up.

    Args:
        limit: Max rows to return (default 50).
    """
    try:
        store = get_instrument_store()
        items = store.list_instruments(limit=limit)
        if not items:
            return json.dumps({
                "status": "not_found",
                "message": (
                    "Milvus collection wm_instruments is empty. "
                    "Run: python -m test.ingest_instruments"
                ),
            }, ensure_ascii=False)
        return json.dumps({
            "status": "success",
            "message": "Instruments available in the Milvus catalog:",
            "data": items,
            "count": len(items),
        }, ensure_ascii=False)
    except Exception as e:
        return _milvus_error(e)


@mcp.tool()
def search_instruments(keyword: str, top_k: int = 8) -> str:
    """
    Semantic search over the Milvus instrument master (ticker, name,
    asset class, sector, keywords, factsheet text).

    Args:
        keyword: Natural-language or ticker keyword, e.g. "AAPL", "treasury", "tech".
        top_k: Max ANN hits to return (default 8).
    """
    try:
        store = get_instrument_store()
        results = store.search(keyword, top_k=top_k)
        if not results:
            return json.dumps({
                "status": "not_found",
                "message": f"No instrument matching '{keyword}' in Milvus.",
                "recommendation": {
                    "instrument_id": "MF_SP500",
                    "name": "S&P 500 Index Fund",
                },
            }, ensure_ascii=False)
        return json.dumps({"status": "success", "data": results}, ensure_ascii=False)
    except Exception as e:
        return _milvus_error(e)


@mcp.tool()
def get_instrument_factsheet(instrument_id: str, user_id: str = "") -> str:
    """
    Return disclosure / factsheet summary for an instrument from Milvus.
    Prefer calling search_instruments first to resolve instrument_id.

    Args:
        instrument_id: Canonical id, e.g. "EQ_AAPL", "BD_UST10Y".
        user_id: [system-injected] client id for audit trail.
    """
    try:
        store = get_instrument_store()
        sheet = store.get_by_id(instrument_id)
        if not sheet:
            return json.dumps({
                "status": "not_found",
                "message": f"No factsheet for instrument_id '{instrument_id}' in Milvus.",
                "recommendation": {"instrument_id": "MF_SP500", "name": "S&P 500 Index Fund"},
            }, ensure_ascii=False)

        return json.dumps({
            "status": "success",
            "data": {
                "instrument_id": sheet["instrument_id"],
                "ticker": sheet.get("ticker"),
                "name": sheet.get("name"),
                "title": sheet.get("title"),
                "summary": sheet.get("summary"),
                "risk_disclosure": sheet.get("risk_disclosure"),
                "asset_class": sheet.get("asset_class"),
                "sector": sheet.get("sector"),
                "currency": sheet.get("currency"),
                "benchmark": sheet.get("benchmark"),
                "factsheet_url": (
                    f"https://wm.internal/factsheets/{instrument_id}?client={user_id}"
                    if user_id else f"https://wm.internal/factsheets/{instrument_id}"
                ),
            },
        }, ensure_ascii=False)
    except Exception as e:
        return _milvus_error(e)


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
