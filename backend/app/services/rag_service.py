import os
import uuid
import logging
from typing import List, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from google import genai

logger = logging.getLogger(__name__)

def get_qdrant_client():
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    return QdrantClient(url=url)

def get_embeddings(texts: List[str]) -> List[List[float]]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")
    client = genai.Client(api_key=api_key)

    vectors = []
    # Gemini embed_content allows batching, but for simplicity we can do it one by one or pass the list if supported
    # In google-genai 0.3.0, embed_content takes a list of strings
    response = client.models.embed_content(
        model='text-embedding-004',
        contents=texts,
    )
    if not isinstance(response.embeddings, list):
        return [response.embeddings[0].values]
    return [emb.values for emb in response.embeddings]

def init_qdrant_collection():
    client = get_qdrant_client()
    collection_name = "modelverse_docs"
    try:
        collections = client.get_collections().collections
        if not any(c.name == collection_name for c in collections):
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )
    except Exception as e:
        logger.error(f"Failed to init Qdrant: {e}")

def ingest_document(project_id: int, title: str, text: str, source_type: str):
    client = get_qdrant_client()
    collection_name = "modelverse_docs"

    # Very basic chunking
    chunk_size = 1000
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    if not chunks:
        return

    try:
        vectors = get_embeddings(chunks)
        points = []
        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "project_id": project_id,
                        "title": title,
                        "text": chunk,
                        "source_type": source_type
                    }
                )
            )
        client.upsert(collection_name=collection_name, points=points)
    except Exception as e:
        logger.error(f"Failed to ingest document to Qdrant: {e}")

def retrieve_context(project_id: int, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    client = get_qdrant_client()
    collection_name = "modelverse_docs"
    try:
        query_vector = get_embeddings([query])[0]
        search_result = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="project_id",
                        match=MatchValue(value=project_id)
                    )
                ]
            ),
            limit=top_k
        )
        return [hit.payload for hit in search_result if hit.payload]
    except Exception as e:
        logger.error(f"Failed to retrieve context from Qdrant: {e}")
        return []
