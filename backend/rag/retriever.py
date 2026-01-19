import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_DIR = os.path.join(BASE_DIR, "db", "chroma_store")

_embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

def get_retriever(k: int = 4):
    vectordb = Chroma(
        collection_name="code_explainer_docs",
        persist_directory=DB_DIR,
        embedding_function=_embeddings
    )
    return vectordb.as_retriever(search_kwargs={"k": k})
