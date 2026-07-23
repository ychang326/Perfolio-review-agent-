"""Milvus-backed instrument master for WM portfolio MCP tools.

Industrial pattern:
- Source of truth: ``mock_data/instruments/instruments.json``
- Serving layer: Milvus collection ``wm_instruments`` (dense vectors + scalar filters)
- Search: embed query → ANN (COSINE)
- Exact lookup / list: Milvus scalar ``query`` (not in-process dict scan)
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

COLLECTION_NAME = "wm_instruments"
EMBEDDING_DIM = 1536
DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "mock_data" / "instruments" / "instruments.json"
)


class GeminiEmbeddings:
    """Google Generative Language embedContent wrapper (OpenAI-compat keys often lack embeddings)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-embedding-001",
        dim: int = EMBEDDING_DIM,
    ) -> None:
        self._api_key = api_key
        self._model = model.removeprefix("models/")
        self._dim = dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # batchEmbedContents accepts multiple requests in one call
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:batchEmbedContents?key={self._api_key}"
        )
        payload = {
            "requests": [
                {
                    "model": f"models/{self._model}",
                    "content": {"parts": [{"text": t}]},
                    "outputDimensionality": self._dim,
                }
                for t in texts
            ]
        }
        data = self._post(url, payload)
        embeddings = data.get("embeddings") or []
        if len(embeddings) != len(texts):
            raise RuntimeError(
                f"Gemini batchEmbedContents returned {len(embeddings)} vectors for {len(texts)} texts"
            )
        return [e["values"] for e in embeddings]

    def embed_query(self, text: str) -> list[float]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:embedContent?key={self._api_key}"
        )
        payload = {
            "model": f"models/{self._model}",
            "content": {"parts": [{"text": text}]},
            "outputDimensionality": self._dim,
        }
        data = self._post(url, payload)
        return data["embedding"]["values"]

    @staticmethod
    def _post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini embedding HTTP {exc.code}: {body[:400]}") from exc


def _create_embeddings(api_key: str) -> Any:
    """Pick embedding backend from env (Gemini when BASE_URL points at Google)."""
    provider = (os.getenv("EMBEDDING_PROVIDER") or "").strip().lower()
    base_url = (os.getenv("BASE_URL") or "").lower()
    model = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")

    if provider in {"dashscope", "alibaba"}:
        from langchain_community.embeddings import DashScopeEmbeddings  # type: ignore[import]

        logger.info("InstrumentStore: using DashScope text-embedding-v2")
        return DashScopeEmbeddings(model="text-embedding-v2", dashscope_api_key=api_key)

    if provider in {"gemini", "google"} or "generativelanguage.googleapis.com" in base_url:
        logger.info("InstrumentStore: using Gemini embeddings (%s, dim=%s)", model, EMBEDDING_DIM)
        return GeminiEmbeddings(api_key=api_key, model=model, dim=EMBEDDING_DIM)

    from langchain_community.embeddings import DashScopeEmbeddings  # type: ignore[import]

    logger.info("InstrumentStore: using DashScope text-embedding-v2 (default)")
    return DashScopeEmbeddings(model="text-embedding-v2", dashscope_api_key=api_key)


def _build_search_text(row: dict[str, Any]) -> str:
    keywords = row.get("keywords") or []
    if isinstance(keywords, list):
        kw = " ".join(str(k) for k in keywords)
    else:
        kw = str(keywords)
    parts = [
        row.get("instrument_id", ""),
        row.get("ticker", ""),
        row.get("name", ""),
        row.get("asset_class", ""),
        row.get("sector", ""),
        kw,
        row.get("title", ""),
        row.get("summary", ""),
        row.get("benchmark", ""),
    ]
    return " | ".join(p for p in parts if p)


def _catalog_to_milvus_row(row: dict[str, Any], embedding: list[float]) -> dict[str, Any]:
    keywords = row.get("keywords") or []
    if isinstance(keywords, list):
        keywords_str = ",".join(str(k) for k in keywords)
    else:
        keywords_str = str(keywords)
    return {
        "instrument_id": str(row["instrument_id"])[:64],
        "ticker": str(row.get("ticker", ""))[:32],
        "name": str(row.get("name", ""))[:256],
        "asset_class": str(row.get("asset_class", ""))[:64],
        "sector": str(row.get("sector", ""))[:64],
        "currency": str(row.get("currency", "USD"))[:16],
        "keywords": keywords_str[:1024],
        "title": str(row.get("title", ""))[:512],
        "summary": str(row.get("summary", ""))[:2048],
        "risk_disclosure": str(row.get("risk_disclosure", ""))[:1024],
        "benchmark": str(row.get("benchmark", ""))[:128],
        "search_text": _build_search_text(row)[:4096],
        "embedding": embedding,
    }


def _public_fields(hit: dict[str, Any], *, include_factsheet: bool = False) -> dict[str, Any]:
    out = {
        "instrument_id": hit.get("instrument_id"),
        "ticker": hit.get("ticker"),
        "name": hit.get("name"),
        "asset_class": hit.get("asset_class"),
        "sector": hit.get("sector"),
        "currency": hit.get("currency"),
    }
    if include_factsheet:
        out.update(
            {
                "title": hit.get("title"),
                "summary": hit.get("summary"),
                "risk_disclosure": hit.get("risk_disclosure"),
                "benchmark": hit.get("benchmark"),
                "keywords": [
                    k for k in str(hit.get("keywords") or "").split(",") if k
                ],
            }
        )
    return out


class InstrumentStore:
    """Milvus instrument catalog client with lazy connect + graceful errors."""

    def __init__(self) -> None:
        self._client: Any = None
        self._embeddings: Any = None
        self._available: bool = False
        self._error: str | None = None

    @property
    def available(self) -> bool:
        return self._available

    @property
    def last_error(self) -> str | None:
        return self._error

    def initialize(self) -> bool:
        """Connect to Milvus and ensure collection schema exists."""
        if self._available:
            return True
        try:
            from pymilvus import MilvusClient  # type: ignore[import]

            host = os.getenv("MILVUS_HOST", "localhost")
            port = os.getenv("MILVUS_PORT", "19530")
            token = os.getenv("MILVUS_API_KEY") or None
            api_key = os.getenv("DASHSCOPE_API_KEY")
            if not api_key:
                raise RuntimeError("DASHSCOPE_API_KEY is required for instrument embeddings")

            uri = f"http://{host}:{port}"
            connect_kwargs: dict[str, Any] = {"uri": uri}
            if token:
                connect_kwargs["token"] = token

            self._client = MilvusClient(**connect_kwargs)
            self._embeddings = _create_embeddings(api_key)
            self._ensure_collection()
            self._available = True
            self._error = None
            logger.info("InstrumentStore: connected to Milvus at %s", uri)
            return True
        except Exception as exc:
            self._available = False
            self._error = str(exc)
            logger.warning("InstrumentStore: Milvus unavailable (%s)", exc)
            return False

    def _ensure_collection(self) -> None:
        from pymilvus import DataType  # type: ignore[import]

        if self._client.has_collection(COLLECTION_NAME):
            return

        schema = self._client.create_schema()
        schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field("instrument_id", DataType.VARCHAR, max_length=64)
        schema.add_field("ticker", DataType.VARCHAR, max_length=32)
        schema.add_field("name", DataType.VARCHAR, max_length=256)
        schema.add_field("asset_class", DataType.VARCHAR, max_length=64)
        schema.add_field("sector", DataType.VARCHAR, max_length=64)
        schema.add_field("currency", DataType.VARCHAR, max_length=16)
        schema.add_field("keywords", DataType.VARCHAR, max_length=1024)
        schema.add_field("title", DataType.VARCHAR, max_length=512)
        schema.add_field("summary", DataType.VARCHAR, max_length=2048)
        schema.add_field("risk_disclosure", DataType.VARCHAR, max_length=1024)
        schema.add_field("benchmark", DataType.VARCHAR, max_length=128)
        schema.add_field("search_text", DataType.VARCHAR, max_length=4096)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)

        index_params = self._client.prepare_index_params()
        index_params.add_index(
            "embedding",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128},
        )

        self._client.create_collection(
            collection_name=COLLECTION_NAME,
            schema=schema,
            index_params=index_params,
        )
        logger.info("InstrumentStore: created collection '%s'", COLLECTION_NAME)

    def ingest_catalog(
        self,
        catalog_path: str | Path | None = None,
        *,
        drop_old: bool = True,
        batch_size: int = 16,
    ) -> int:
        """Embed and upsert instruments from JSON catalog into Milvus."""
        if not self.initialize():
            raise RuntimeError(f"Milvus unavailable: {self._error}")

        path = Path(catalog_path) if catalog_path else DEFAULT_CATALOG_PATH
        with path.open(encoding="utf-8") as f:
            rows: list[dict[str, Any]] = json.load(f)
        if not rows:
            raise ValueError(f"Empty instrument catalog: {path}")

        if drop_old and self._client.has_collection(COLLECTION_NAME):
            self._client.drop_collection(COLLECTION_NAME)
            self._ensure_collection()

        texts = [_build_search_text(r) for r in rows]
        inserted = 0
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_rows = rows[i : i + batch_size]
            vectors = self._embeddings.embed_documents(batch_texts)
            payload = [
                _catalog_to_milvus_row(row, emb)
                for row, emb in zip(batch_rows, vectors)
            ]
            self._client.insert(collection_name=COLLECTION_NAME, data=payload)
            inserted += len(payload)

        try:
            self._client.flush(COLLECTION_NAME)
        except Exception:
            # Some MilvusClient versions auto-flush; ignore if unsupported.
            pass
        logger.info("InstrumentStore: ingested %s instruments from %s", inserted, path)
        return inserted

    def count(self) -> int:
        if not self.initialize():
            return 0
        try:
            stats = self._client.get_collection_stats(COLLECTION_NAME)
            return int(stats.get("row_count") or stats.get("rowCount") or 0)
        except Exception:
            # Fallback: bounded query
            rows = self._client.query(
                collection_name=COLLECTION_NAME,
                filter='instrument_id != ""',
                output_fields=["instrument_id"],
                limit=16384,
            )
            return len(rows)

    def list_instruments(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.initialize():
            raise RuntimeError(f"Milvus unavailable: {self._error}")
        rows = self._client.query(
            collection_name=COLLECTION_NAME,
            filter='instrument_id != ""',
            output_fields=[
                "instrument_id",
                "ticker",
                "name",
                "asset_class",
                "sector",
                "currency",
            ],
            limit=max(1, min(limit, 16384)),
        )
        return [_public_fields(r) for r in rows]

    def search(self, keyword: str, top_k: int = 8) -> list[dict[str, Any]]:
        if not self.initialize():
            raise RuntimeError(f"Milvus unavailable: {self._error}")
        query = (keyword or "").strip()
        if not query:
            return []

        vector = self._embeddings.embed_query(query)
        hits = self._client.search(
            collection_name=COLLECTION_NAME,
            data=[vector],
            limit=max(1, min(top_k, 32)),
            output_fields=[
                "instrument_id",
                "ticker",
                "name",
                "asset_class",
                "sector",
                "currency",
            ],
            search_params={"metric_type": "COSINE", "params": {"nprobe": 16}},
        )
        results: list[dict[str, Any]] = []
        for group in hits:
            for hit in group:
                entity = hit.get("entity") or hit
                item = _public_fields(entity)
                # MilvusClient returns distance; for COSINE lower distance ≈ more similar
                # depending on version — expose raw score for debugging.
                if "distance" in hit:
                    item["distance"] = float(hit["distance"])
                elif "score" in hit:
                    item["distance"] = float(hit["score"])
                results.append(item)
        return results

    def get_by_id(self, instrument_id: str) -> dict[str, Any] | None:
        if not self.initialize():
            raise RuntimeError(f"Milvus unavailable: {self._error}")
        iid = (instrument_id or "").strip()
        if not iid:
            return None
        # Escape double quotes in filter literal
        safe = iid.replace('\\', '\\\\').replace('"', '\\"')
        rows = self._client.query(
            collection_name=COLLECTION_NAME,
            filter=f'instrument_id == "{safe}"',
            output_fields=[
                "instrument_id",
                "ticker",
                "name",
                "asset_class",
                "sector",
                "currency",
                "keywords",
                "title",
                "summary",
                "risk_disclosure",
                "benchmark",
            ],
            limit=1,
        )
        if not rows:
            return None
        return _public_fields(rows[0], include_factsheet=True)


_store: InstrumentStore | None = None


def get_instrument_store() -> InstrumentStore:
    global _store
    if _store is None:
        _store = InstrumentStore()
    return _store
