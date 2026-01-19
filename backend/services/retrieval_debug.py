from typing import List, Dict
from backend.rag.retriever import get_retriever

def debug_retrieval(query: str, k: int = 4) -> List[Dict]:
    try:
        retriever = get_retriever(k=k)
    except TypeError:
        retriever = get_retriever()

    try:
        docs = retriever.invoke(query)
    except Exception:
        docs = retriever.get_relevant_documents(query)

    results = []
    for d in docs:
        results.append({
            "source": (d.metadata or {}).get("source", "unknown"),
            "preview": (d.page_content or "")[:350]
        })

    return results
