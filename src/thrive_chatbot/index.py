"""Build and refresh the local vector index (Chroma). Vectors are computed ahead of time and only
re-computed for articles whose text changed, so refreshing after a sheet edit is cheap."""
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from . import config
from .data import Article


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    # Normalized vectors make cosine similarity a plain dot product. Runs locally, no API key.
    return HuggingFaceEmbeddings(
        model_name=config.EMBED_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )


def get_store() -> Chroma:
    # Swapping to Pinecone later only changes this function (e.g. PineconeVectorStore).
    return Chroma(
        collection_name=config.COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=str(config.CHROMA_DIR),
        collection_metadata={"hnsw:space": "cosine"},
    )


def _to_document(a: Article) -> Document:
    return Document(
        page_content=a.text,
        metadata={
            "title": a.title,
            "authors": a.authors,
            "link": a.link,
            "categories": " | ".join(a.categories),
            "hash": a.content_hash,
        },
    )


def refresh_index(articles: list[Article], store: Chroma | None = None) -> dict[str, int]:
    """Make the index match `articles`. Returns counts of added / updated / removed / unchanged."""
    store = store or get_store()
    existing = store.get(include=["metadatas"])
    old = {i: (m or {}).get("hash") for i, m in zip(existing["ids"], existing["metadatas"])}
    new = {a.id: a for a in articles}

    removed = [i for i in old if i not in new]
    changed = [i for i, a in new.items() if old.get(i) != a.content_hash]

    if removed:
        store.delete(ids=removed)
    if changed:
        store.add_documents([_to_document(new[i]) for i in changed], ids=changed)  # upserts by id

    added = sum(1 for i in changed if i not in old)
    return {
        "added": added,
        "updated": len(changed) - added,
        "removed": len(removed),
        "unchanged": len(new) - len(changed),
    }
