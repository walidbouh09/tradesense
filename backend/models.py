from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    email = Column(String(256), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    portfolios = relationship('Portfolio', back_populates='owner')


class Portfolio(Base):
    __tablename__ = 'portfolios'
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    owner_id = Column(Integer, ForeignKey('users.id'))
    owner = relationship('User', back_populates='portfolios')
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Trade(Base):
    __tablename__ = 'trades'
    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey('portfolios.id'))
    symbol = Column(String(64), nullable=False)
    qty = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    side = Column(String(4), nullable=False)  # BUY/SELL
    executed_at = Column(DateTime, default=datetime.datetime.utcnow)
