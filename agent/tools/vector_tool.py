import os
import json
from dotenv import load_dotenv
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_milvus import Milvus
from pymilvus import connections
from langchain_core.tools import tool

# ==============================================================================
# 修复 pymilvus 2.6.x 与 langchain-milvus 0.3.x 之间的兼容性问题
# ==============================================================================
original_fetch = connections._fetch_handler
def patched_fetch(alias):
    try:
        return original_fetch(alias)
    except Exception:
        from pymilvus.client.connection_manager import ConnectionManager
        mgr = ConnectionManager.get_instance()
        for mc in mgr._registry.values():
            if f"cm-{id(mc.handler)}" == alias:
                return mc.handler
        for mc in mgr._dedicated.values():
            if f"cm-{id(mc.handler)}" == alias:
                return mc.handler
        raise
connections._fetch_handler = patched_fetch
# ==============================================================================

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path)

_milvus_instance = None

def _get_milvus_store():
    global _milvus_instance
    if _milvus_instance is not None:
        return _milvus_instance

    api_key = os.getenv("DASHSCOPE_API_KEY")
    milvus_host = os.getenv("MILVUS_HOST", "localhost")
    milvus_port = os.getenv("MILVUS_PORT", "19530")
    milvus_uri = f"http://{milvus_host}:{milvus_port}"

    print(f"🔌 [Init] 正在连接 Milvus 向量数据库: {milvus_uri}")
    embeddings = DashScopeEmbeddings(
        dashscope_api_key=api_key,
        model="text-embedding-v2"
    )

    _milvus_instance = Milvus(
        embedding_function=embeddings,
        connection_args={"uri": milvus_uri},
        collection_name="wm_portfolio_docs",
        auto_id=True,
        drop_old=False
    )
    return _milvus_instance

@tool
def query_vector_db(query: str) -> str:
    """
    Semantic search over wealth-management education docs (RAG).
    Use for concepts such as asset allocation, concentration risk, TWR/XIRR, disclosures.
    """
    try:
        store = _get_milvus_store()
        results = store.similarity_search_with_score(query, k=3)
        
        if not results:
            return "No relevant documents were found."

        formatted_results = []
        for i, (doc, score) in enumerate(results):
            source = os.path.basename(doc.metadata.get('source', 'Unknown'))
            content = doc.page_content.strip()
            formatted_results.append(f"【Source: {source}】\n{content}")
            
        return "\n\n".join(formatted_results)
    except Exception as e:
        return f"Error querying the vector database: {str(e)}"
