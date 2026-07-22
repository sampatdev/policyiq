from sqlalchemy import Column, Integer, String, Text
from pgvector.sqlalchemy import Vector
from app.db import Base

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True)
    document_name = Column(String, nullable=False)   # e.g. "health_policy_v1.pdf"
    chunk_text = Column(Text, nullable=False)          # the actual paragraph of text
    embedding = Column(Vector(1024))                   # the number-list representing its meaning