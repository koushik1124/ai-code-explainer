import os
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR.parents[0] / "data" / "docs"
DB_DIR = BASE_DIR / "db" / "chroma_store"

def ingest_docs():
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"Docs folder not found: {DATA_DIR}")

    loader = DirectoryLoader(
        str(DATA_DIR),
        glob="**/*.*",
        loader_cls=TextLoader,
        show_progress=True,
        loader_kwargs={"encoding": "utf-8"},
    )
    docs = loader.load()

    # Remove empty docs
    docs = [d for d in docs if (d.page_content or "").strip()]
    if not docs:
        raise ValueError("No valid documents found in data/docs.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=150,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(docs)

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    vectordb = Chroma(
        collection_name="code_explainer_docs",
        persist_directory=str(DB_DIR),
        embedding_function=embeddings,
    )

    # Reset collection before ingest (clean rebuild)
    try:
        vectordb.delete_collection()
    except Exception:
        pass

    vectordb = Chroma(
        collection_name="code_explainer_docs",
        persist_directory=str(DB_DIR),
        embedding_function=embeddings,
    )

    vectordb.add_documents(chunks)
    #vectordb.persist()

    print(f"✅ Ingested {len(chunks)} chunks into ChromaDB at {DB_DIR}")

if __name__ == "__main__":
    ingest_docs()
