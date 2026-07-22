from fastapi import FastAPI, UploadFile, Depends
from sqlalchemy.orm import Session
import shutil

from app.db import engine, Base, get_db
from app import models
from app.ingestion import extract_text_from_pdf, chunk_text, embed_chunks
from app.query import embed_query, search_similar_chunks, ask_claude
from app.agent import run_agent

app = FastAPI(title="PolicyIQ")

Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/ingest")
async def ingest_document(file: UploadFile, db: Session = Depends(get_db)):
    # Save the uploaded file temporarily so pypdf can read it from disk
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    text = extract_text_from_pdf(temp_path)
    chunks = chunk_text(text)
    embeddings = embed_chunks(chunks)

    for chunk_text_content, embedding in zip(chunks, embeddings):
        record = models.DocumentChunk(
            document_name=file.filename,
            chunk_text=chunk_text_content,
            embedding=embedding,
        )
        db.add(record)
    db.commit()

    return {"filename": file.filename, "chunks_created": len(chunks)}


@app.post("/query")
def query_documents(question: str, db: Session = Depends(get_db)):
    query_embedding = embed_query(question)
    chunks = search_similar_chunks(db, query_embedding)

    if not chunks:
        return {"answer": "No documents have been ingested yet.", "sources": []}

    answer = ask_claude(question, chunks)

    return {
        "answer": answer,
        "sources": [{"document": row.document_name, "distance": row.distance} for row in chunks],
    }



@app.post("/agent-query")
def agent_query(question: str, db: Session = Depends(get_db)):
    return run_agent(db, question)