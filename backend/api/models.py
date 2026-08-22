from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class Entity(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    category = Column(String(100), default="Policy")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    claims = relationship("Claim", back_populates="entity", cascade="all, delete-orphan")
    comparisons = relationship("Comparison", back_populates="entity", cascade="all, delete-orphan")

class Claim(Base):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    claim_text = Column(Text, nullable=False)
    effective_date = Column(String(50), nullable=True)
    document_title = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    entity = relationship("Entity", back_populates="claims")

class Comparison(Base):
    __tablename__ = "comparisons"

    id = Column(Integer, primary_key=True, index=True)
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    shift_summary = Column(Text, nullable=False)
    mechanism = Column(Text, nullable=False)
    impact_summary = Column(Text, nullable=False)
    confidence_score = Column(Float, default=0.90)
    claim_a_id = Column(Integer, ForeignKey("claims.id", ondelete="SET NULL"), nullable=True)
    claim_b_id = Column(Integer, ForeignKey("claims.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="investigator")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class UserSearchHistory(Base):
    __tablename__ = "user_search_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), index=True, nullable=False)
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    entity_name = Column(String(255), nullable=False)
    contradiction_count = Column(Integer, default=0)
    comparison_count = Column(Integer, default=0)
    searched_at = Column(DateTime(timezone=True), server_default=func.now())
