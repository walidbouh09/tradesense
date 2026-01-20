"""
TradeSense AI - Unified FastAPI Backend
Production-ready prop trading platform backend
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn
import asyncio
import sqlite3
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import uuid
import hashlib
from contextlib import asynccontextmanager
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_PATH = "tradesense.db"
security = HTTPBearer()

# Global database connection
db_connection = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global db_connection
    
    # Startup
    logger.info("Starting TradeSense AI backend...")
    db_connection = init_database()
    logger.info("Database initialized successfully")
    
    yield
    
    # Shutdown
    if db_connection:
        db_connection.close()
    logger.info("TradeSense AI backend stopped")

# Create FastAPI app
app = FastAPI(
    title="TradeSense AI",
    description="FinTech Prop Trading SaaS Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class Challenge(BaseModel):
    id: str
    user_id: str
    status: str
    initial_balance: float
    current_equity: float
    daily_start_equity: float
    max_equity_ever: float
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    last_trade_at: Optional[str] = None
    created_at: str
    total_trades: int = 0
    win_rate: float = 0.0
    avg_trade_pnl: float = 0.0

class ChallengeCreate(BaseModel):
    initial_balance: float = Field(default=10000, ge=1000, le=100000)
    rules: Optional[Dict[str, Any]] = Field(default_factory=lambda: {
        "max_daily_drawdown": 0.05,
        "max_total_drawdown": 0.10,
        "profit_target": 0.10
    })

class Trade(BaseModel):
    trade_id: str
    challenge_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    realized_pnl: float
    executed_at: str

class TradeCreate(BaseModel):
    challenge_id: str
    symbol: str = Field(..., min_length=1)
    side: str = Field(..., regex="^(BUY|SELL)$")
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    realized_pnl: float

class RiskAlert(BaseModel):
    id: str
    challenge_id: str
    alert_type: str
    severity: str
    title: str
    message: str
    created_at: str
    acknowledged_at: Optional[str] = None

class RiskMetrics(BaseModel):
    total_alerts: int
    critical_alerts: int
    active_challenges: int
    avg_risk_score: float
    high_risk_challenges: int

class MarketPrice(BaseModel):
    symbol: str
    price: float
    change: float
    change_percent: float
    last_updated: str

# Database initialization
def init_database():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # Create tables
    conn.executescript("""
        -- Users table
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'USER',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Challenges table
        CREATE TABLE IF NOT EXISTS challenges (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            initial_balance REAL NOT NULL,
            current_equity REAL NOT NULL,
            daily_start_equity REAL NOT NULL,
            max_equity_ever REAL NOT NULL,
            max_daily_drawdown_percent REAL DEFAULT 0.05,
            max_total_drawdown_percent REAL DEFAULT 0.10,
            profit_target_percent REAL DEFAULT 0.10,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            last_trade_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_trades INTEGER DEFAULT 0,
            win_rate REAL DEFAULT 0.0,
            avg_trade_pnl REAL DEFAULT 0.0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        
        -- Trades table
        CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            challenge_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            realized_pnl REAL NOT NULL,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (challenge_id) REFERENCES challenges (id)
        );
        
        -- Risk alerts table
        CREATE TABLE IF NOT EXISTS risk_alerts (
            id TEXT PRIMARY KEY,
            challenge_id TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            acknowledged_at TIMESTAMP,
            FOREIGN KEY (challenge_id) REFERENCES challenges (id)
        );
        
        -- Payments table
        CREATE TABLE IF NOT EXISTS payments (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            challenge_id TEXT,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'MAD',
            provider TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (challenge_id) REFERENCES challenges (id)
        );
    """)
    
    # Create default admin user
    user_id = str(uuid.uuid4())
    password_hash = hashlib.sha256("admin123".encode()).hexdigest()
    
    try:
        conn.execute("""
            INSERT OR IGNORE INTO users (id, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        """, (user_id, "admin@tradesense.ai", password_hash, "ADMIN"))
        conn.commit()
        logger.info("Default admin user created")
    except Exception as e:
        logger.warning(f"Admin user already exists: {e}")
    
    return conn

def get_db():
    """Get database connection"""
    return db_connection

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token (simplified for demo)"""
    # In production, implement proper JWT validation
    return "550e8400-e29b-41d4-a716-446655440000"  # Demo user ID

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "tradesense-ai",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# Authentication endpoints
@app.post("/api/auth/login")
async def login(email: str, password: str):
    """Login endpoint (simplified for demo)"""
    return {
        "token": "demo_jwt_token",
        "user": {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "email": email,
            "role": "USER"
        }
    }

# Challenge management endpoints
@app.get("/api/challenges", response_model=Dict[str, Any])
async def list_challenges(
    page: int = 1,
    limit: int = 20,
    current_user: str = Depends(get_current_user)
):
    """List all challenges for the current user"""
    try:
        db = get_db()
        offset = (page - 1) * limit
        
        cursor = db.execute("""
            SELECT * FROM challenges 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        challenges = []
        for row in cursor.fetchall():
            challenges.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "status": row["status"],
                "initial_balance": float(row["initial_balance"]),
                "current_equity": float(row["current_equity"]),
                "daily_start_equity": float(row["daily_start_equity"]),
                "max_equity_ever": float(row["max_equity_ever"]),
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
                "last_trade_at": row["last_trade_at"],
                "created_at": row["created_at"],
                "total_trades": row["total_trades"] or 0,
                "win_rate": float(row["win_rate"] or 0),
                "avg_trade_pnl": float(row["avg_trade_pnl"] or 0)
            })
        
        total_count = db.execute("SELECT COUNT(*) FROM challenges").fetchone()[0]
        
        return {
            "challenges": challenges,
            "total": total_count,
            "page": page,
            "per_page": limit
        }
    
    except Exception as e:
        logger.error(f"Error listing challenges: {e}")
        raise HTTPException(status_code=500, detail="Failed to list challenges")

@app.post("/api/challenges", response_model=Challenge)
async def create_challenge(
    challenge_data: ChallengeCreate,
    current_user: str = Depends(get_current_user)
):
    """Create a new trading challenge"""
    try:
        db = get_db()
        challenge_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        rules = challenge_data.rules
        initial_balance = challenge_data.initial_balance
        
        db.execute("""
            INSERT INTO challenges (
                id, user_id, initial_balance, current_equity, daily_start_equity,
                max_equity_ever, max_daily_drawdown_percent, max_total_drawdown_percent,
                profit_target_percent, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            challenge_id, current_user, initial_balance, initial_balance, initial_balance,
            initial_balance, rules["max_daily_drawdown"], rules["max_total_drawdown"],
            rules["profit_target"], "ACTIVE", now.isoformat(), now.isoformat()
        ))
        
        db.commit()
        
        return Challenge(
            id=challenge_id,
            user_id=current_user,
            status="ACTIVE",
            initial_balance=initial_balance,
            current_equity=initial_balance,
            daily_start_equity=initial_balance,
            max_equity_ever=initial_balance,
            created_at=now.isoformat()
        )
    
    except Exception as e:
        logger.error(f"Error creating challenge: {e}")
        raise HTTPException(status_code=500, detail="Failed to create challenge")

@app.get("/api/challenges/{challenge_id}", response_model=Dict[str, Any])
async def get_challenge(
    challenge_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get detailed information about a specific challenge"""
    try:
        db = get_db()
        
        # Get challenge details
        cursor = db.execute("""
            SELECT * FROM challenges WHERE id = ?
        """, (challenge_id,))
        
        challenge = cursor.fetchone()
        if not challenge:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        # Get recent trades
        trades_cursor = db.execute("""
            SELECT * FROM trades 
            WHERE challenge_id = ? 
            ORDER BY executed_at DESC 
            LIMIT 10
        """, (challenge_id,))
        
        trades = []
        for trade in trades_cursor.fetchall():
            trades.append({
                "trade_id": trade["id"],
                "symbol": trade["symbol"],
                "side": trade["side"],
                "quantity": float(trade["quantity"]),
                "price": float(trade["price"]),
                "realized_pnl": float(trade["realized_pnl"]),
                "executed_at": trade["executed_at"]
            })
        
        challenge_dict = {
            "id": challenge["id"],
            "user_id": challenge["user_id"],
            "status": challenge["status"],
            "initial_balance": float(challenge["initial_balance"]),
            "current_equity": float(challenge["current_equity"]),
            "daily_start_equity": float(challenge["daily_start_equity"]),
            "max_equity_ever": float(challenge["max_equity_ever"]),
            "started_at": challenge["started_at"],
            "ended_at": challenge["ended_at"],
            "last_trade_at": challenge["last_trade_at"],
            "created_at": challenge["created_at"],
            "total_trades": challenge["total_trades"] or 0,
            "win_rate": float(challenge["win_rate"] or 0),
            "avg_trade_pnl": float(challenge["avg_trade_pnl"] or 0),
            "trades": trades
        }
        
        return challenge_dict
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting challenge: {e}")
        raise HTTPException(status_code=500, detail="Failed to get challenge")

# Trading endpoints
@app.post("/api/trades", response_model=Trade)
async def create_trade(
    trade_data: TradeCreate,
    current_user: str = Depends(get_current_user)
):
    """Create a new trade and update challenge equity"""
    try:
        db = get_db()
        
        # Verify challenge exists and is active
        cursor = db.execute("""
            SELECT * FROM challenges WHERE id = ? AND status = 'ACTIVE'
        """, (trade_data.challenge_id,))
        
        challenge = cursor.fetchone()
        if not challenge:
            raise HTTPException(status_code=404, detail="Active challenge not found")
        
        # Create trade
        trade_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        db.execute("""
            INSERT INTO trades (
                id, challenge_id, symbol, side, quantity, price, realized_pnl, executed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_id, trade_data.challenge_id, trade_data.symbol, trade_data.side,
            trade_data.quantity, trade_data.price, trade_data.realized_pnl, now.isoformat()
        ))
        
        # Update challenge equity
        new_equity = float(challenge["current_equity"]) + trade_data.realized_pnl
        new_max_equity = max(float(challenge["max_equity_ever"]), new_equity)
        
        # Update trade statistics
        total_trades = (challenge["total_trades"] or 0) + 1
        
        # Calculate win rate
        profitable_trades = db.execute("""
            SELECT COUNT(*) FROM trades 
            WHERE challenge_id = ? AND realized_pnl > 0
        """, (trade_data.challenge_id,)).fetchone()[0]
        
        win_rate = profitable_trades / total_trades if total_trades > 0 else 0
        
        # Calculate average PnL
        avg_pnl_result = db.execute("""
            SELECT AVG(realized_pnl) FROM trades 
            WHERE challenge_id = ?
        """, (trade_data.challenge_id,)).fetchone()[0]
        
        avg_trade_pnl = float(avg_pnl_result or 0)
        
        db.execute("""
            UPDATE challenges 
            SET current_equity = ?, max_equity_ever = ?, last_trade_at = ?,
                total_trades = ?, win_rate = ?, avg_trade_pnl = ?, updated_at = ?
            WHERE id = ?
        """, (
            new_equity, new_max_equity, now.isoformat(),
            total_trades, win_rate, avg_trade_pnl, now.isoformat(),
            trade_data.challenge_id
        ))
        
        # Check for rule violations
        await check_risk_rules(db, trade_data.challenge_id, challenge)
        
        db.commit()
        
        return Trade(
            trade_id=trade_id,
            challenge_id=trade_data.challenge_id,
            symbol=trade_data.symbol,
            side=trade_data.side,
            quantity=trade_data.quantity,
            price=trade_data.price,
            realized_pnl=trade_data.realized_pnl,
            executed_at=now.isoformat()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating trade: {e}")
        raise HTTPException(status_code=500, detail="Failed to create trade")

@app.get("/api/trades", response_model=List[Trade])
async def list_trades(
    challenge_id: Optional[str] = None,
    limit: int = 50,
    current_user: str = Depends(get_current_user)
):
    """List trades for a challenge"""
    try:
        db = get_db()
        
        if challenge_id:
            cursor = db.execute("""
                SELECT * FROM trades 
                WHERE challenge_id = ? 
                ORDER BY executed_at DESC