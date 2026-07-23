"""Ingest WM instrument master into Milvus collection ``wm_instruments``.

Usage (from ``agent/`` with venv active)::

    python -m test.ingest_instruments
    python -m test.ingest_instruments --catalog ../mock_data/instruments/instruments.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path)

# Allow ``python -m test.ingest_instruments`` from agent/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_servers.instrument_store import (  # noqa: E402
    DEFAULT_CATALOG_PATH,
    get_instrument_store,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest instruments into Milvus")
    parser.add_argument(
        "--catalog",
        default=str(DEFAULT_CATALOG_PATH),
        help="Path to instruments.json",
    )
    parser.add_argument(
        "--keep-old",
        action="store_true",
        help="Do not drop the existing collection before ingest",
    )
    args = parser.parse_args()

    store = get_instrument_store()
    try:
        n = store.ingest_catalog(args.catalog, drop_old=not args.keep_old)
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1

    sample = store.search("technology equity apple", top_k=3)
    print(
        json.dumps(
            {
                "status": "success",
                "ingested": n,
                "collection_count": store.count(),
                "sample_search": sample,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
