"""SQLAlchemy models for trading domain."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class OrderModel(Base):
    """SQLAlchemy model for Order aggregate."""
    
    __tablename__ = "orders"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    user_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    order_type = Column(String(20), nullable=False)
    quantity = Column(String(50), nullable=False)  # Store as string to preserve precision
    price = Column(String(50), nullable=True)
    stop_price = Column(String(50), nullable=True)
    time_in_force = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, index=True)
    filled_quantity = Column(String(50), nullable=False, default="0")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<OrderModel(id={self.id}, symbol={self.symbol}, status={self.status})>"


class FillModel(Base):
    """SQLAlchemy model for order fills."""
    
    __tablename__ = "fills"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    order_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    fill_id = Column(String(100), nullable=False, unique=True)
    quantity = Column(String(50), nullable=False)
    price = Column(String(50), nullable=False)
    timestamp = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<FillModel(id={self.id}, order_id={self.order_id}, fill_id={self.fill_id})>"