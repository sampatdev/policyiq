from sqlalchemy import text
from sqlalchemy.orm import Session
import anthropic
import voyageai

from app.config import settings

voyage_client = voyageai.Client(api_key=settings.voyage_api_key)
claude_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def embed_query(question: str) -> list[float]:
    """Embed the user's question — note input_type='query', not 'document'."""
    result = voyage_client.embed([question], model="voyage-2", input_type="query")
    return result.embeddings[0]


def search_similar_chunks(db: Session, query_embedding: list[float], top_k: int = 5):
    """
    Find the top_k chunks whose stored embedding is closest to the query embedding.
    <=> is pgvector's cosine distance operator — smaller value means more similar.
    We cast the Python list to a string pgvector understands: '[0.1, 0.2, ...]'
    """
    embedding_str = str(query_embedding)
    sql = text("""
        SELECT document_name, chunk_text, embedding <=> :query_embedding AS distance
        FROM document_chunks
        ORDER BY distance
        LIMIT :top_k
    """)
    result = db.execute(sql, {"query_embedding": embedding_str, "top_k": top_k})
    return result.fetchall()


def ask_claude(question: str, retrieved_chunks: list) -> str:
    """Build a grounded prompt from retrieved chunks and ask Claude to answer."""
    context = "\n\n---\n\n".join(
        f"[From: {row.document_name}]\n{row.chunk_text}" for row in retrieved_chunks
    )

    prompt = f"""Answer the question using ONLY the context below. If the context doesn't contain the answer, say "I don't have enough information to answer that" — do not guess.

Context:
{context}

Question: {question}"""

    response = claude_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text