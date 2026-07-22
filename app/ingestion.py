from pypdf import PdfReader
import voyageai
from app.config import settings
import time

voyage_client = voyageai.Client(api_key=settings.voyage_api_key)


def extract_text_from_pdf(file_path: str) -> str:
    """Pull all readable text out of a PDF, page by page."""
    reader = PdfReader(file_path)
    full_text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        full_text += page_text + "\n"
    return full_text.replace("\x00", "")  # strip null bytes — Postgres TEXT can't store them


def chunk_text(text: str, chunk_size_words: int = 400, overlap_words: int = 50) -> list[str]:
    """
    Split text into overlapping word-based chunks.
    Overlap means the tail of one chunk reappears at the start of the next,
    so a sentence sitting on a chunk boundary doesn't get cut in half.
    """
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size_words
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size_words - overlap_words  # step forward, leaving overlap behind
    return chunks


def embed_chunks(chunks: list[str], batch_size: int = 3, delay_seconds: int = 21) -> list[list[float]]:
    """
    Send chunks to Voyage's embedding model in small batches, with a delay
    between batches, to stay under the free tier's request-rate and
    token-volume limits without needing a payment method on file.
    """
    all_embeddings = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        result = voyage_client.embed(batch, model="voyage-2", input_type="document")
        all_embeddings.extend(result.embeddings)

        # Don't sleep after the very last batch — no point waiting when there's nothing left to send
        if i + batch_size < len(chunks):
            time.sleep(delay_seconds)

    return all_embeddings