#!/usr/bin/env python3
"""
TradeSense AI - Simplified Backend Application

A simplified version of the TradeSense AI backend that works with minimal dependencies
for quick demo and testing purposes.
"""

import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, List, Optional

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from marshmallow import Schema, ValidationError, fields
from werkzeug.security import check_password_hash, generate_password_hash

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY", "dev-secret-key-change-in-production"
)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///tradesense_demo.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions
db = SQLAlchemy(app)
CORS(
    app,
    origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"],
)

# Simple token storage (in production, use Redis or database)
active_tokens = set()


# Database Models
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default="trader", nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False)
    is_verified = db.Column(db.Boolean, default=True, nullable=False)
    experience_level = db.Column(db.String(20), default="beginner")
    country = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime)

    # Relationships
    portfolios = db.relationship(
        "Portfolio", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    trades = db.relationship(
        "Trade", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "role": self.role,
            "status": self.status,
            "is_verified": self.is_verified,
            "experience_level": self.experience_level,
            "country": self.country,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class Portfolio(db.Model):
    __tablename__ = "portfolios"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    initial_balance = db.Column(db.Float, nullable=False, default=10000.0)
    current_balance = db.Column(db.Float, nullable=False, default=10000.0)
    total_pnl = db.Column(db.Float, default=0.0)
    total_trades = db.Column(db.Integer, default=0)
    winning_trades = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_demo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    trades = db.relationship(
        "Trade", backref="portfolio", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def win_rate(self):
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100

    @property
    def return_percentage(self):
        if self.initial_balance == 0:
            return 0.0
        return (
            (self.current_balance - self.initial_balance) / self.initial_balance
        ) * 100

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "initial_balance": self.initial_balance,
            "current_balance": self.current_balance,
            "total_pnl": self.total_pnl,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate": self.win_rate,
            "return_percentage": self.return_percentage,
            "is_active": self.is_active,
            "is_demo": self.is_demo,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Trade(db.Model):
    __tablename__ = "trades"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    portfolio_id = db.Column(db.Integer, db.ForeignKey("portfolios.id"), nullable=False)
    symbol = db.Column(db.String(20), nullable=False, index=True)
    side = db.Column(db.String(10), nullable=False)  # buy, sell
    order_type = db.Column(db.String(20), nullable=False)  # market, limit
    status = db.Column(db.String(20), default="executed", nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float)
    executed_price = db.Column(db.Float)
    pnl = db.Column(db.Float, default=0.0)
    commission = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    executed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "portfolio_id": self.portfolio_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "status": self.status,
            "quantity": self.quantity,
            "price": self.price,
            "executed_price": self.executed_price,
            "pnl": self.pnl,
            "commission": self.commission,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }


class Challenge(db.Model):
    __tablename__ = "challenges"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    initial_balance = db.Column(db.Float, nullable=False)
    target_profit = db.Column(db.Float, nullable=False)
    max_loss = db.Column(db.Float, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False)
    current_balance = db.Column(db.Float, default=0.0)
    current_pnl = db.Column(db.Float, default=0.0)
    total_trades = db.Column(db.Integer, default=0)
    winning_trades = db.Column(db.Integer, default=0)
    entry_fee = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)

    user = db.relationship("User", backref="challenges")

    @property
    def progress_percentage(self):
        if self.target_profit == 0:
            return 0.0
        return (self.current_pnl / self.target_profit) * 100

    @property
    def win_rate(self):
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "initial_balance": self.initial_balance,
            "target_profit": self.target_profit,
            "max_loss": self.max_loss,
            "duration_days": self.duration_days,
            "status": self.status,
            "current_balance": self.current_balance,
            "current_pnl": self.current_pnl,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate": self.win_rate,
            "progress_percentage": self.progress_percentage,
            "entry_fee": self.entry_fee,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
        }


# Validation Schemas
class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)
    remember_me = fields.Bool(load_default=False)


class RegisterSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)
    confirm_password = fields.Str(required=True)
    first_name = fields.Str(required=True)
    last_name = fields.Str(required=True)
    phone = fields.Str(allow_none=True)
    country = fields.Str(allow_none=True)
    experience_level = fields.Str(load_default="beginner")
    terms_accepted = fields.Bool(required=True)


class TradeSchema(Schema):
    symbol = fields.Str(required=True)
    side = fields.Str(required=True, validate=lambda x: x in ["buy", "sell"])
    quantity = fields.Float(required=True, validate=lambda x: x > 0)
    order_type = fields.Str(required=True, validate=lambda x: x in ["market", "limit"])
    price = fields.Float(allow_none=True)
    stop_loss = fields.Float(allow_none=True)
    take_profit = fields.Float(allow_none=True)


# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")

        if auth_header:
            try:
                token = auth_header.split(" ")[1]  # Bearer <token>
            except IndexError:
                return jsonify(
                    {
                        "error": {
                            "code": "INVALID_TOKEN",
                            "message": "Invalid token format",
                        }
                    }
                ), 401

        if not token or token not in active_tokens:
            return jsonify(
                {
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Token is missing or invalid",
                    }
                }
            ), 401

        # Get user from token (simplified - in production use JWT)
        user = User.query.filter_by(
            email=token
        ).first()  # Using email as token for demo
        if not user:
            return jsonify(
                {"error": {"code": "USER_NOT_FOUND", "message": "User not found"}}
            ), 401

        g.current_user = user
        return f(*args, **kwargs)

    return decorated


# Helper functions
def create_sample_data():
    """Create sample data for demo."""
    # Create admin user
    admin = User.query.filter_by(email="admin@tradesense.ai").first()
    if not admin:
        admin = User(
            email="admin@tradesense.ai",
            first_name="Admin",
            last_name="TradeSense",
            role="admin",
        )
        admin.set_password("admin123456")
        db.session.add(admin)

    # Create demo trader
    demo_trader = User.query.filter_by(email="demo.trader@tradesense.ai").first()
    if not demo_trader:
        demo_trader = User(
            email="demo.trader@tradesense.ai",
            first_name="Demo",
            last_name="Trader",
            role="trader",
            experience_level="intermediate",
            country="USA",
        )
        demo_trader.set_password("demo123456")
        db.session.add(demo_trader)
        db.session.commit()

        # Create demo portfolio
        portfolio = Portfolio(
            name="Demo Trading Portfolio",
            description="Demo portfolio for testing and development",
            user_id=demo_trader.id,
            initial_balance=10000.0,
            current_balance=10000.0,
        )
        db.session.add(portfolio)

        # Create demo challenge
        challenge = Challenge(
            name="Beginner Trading Challenge",
            description="Perfect for new traders to test their skills",
            user_id=demo_trader.id,
            initial_balance=5000.0,
            target_profit=400.0,
            max_loss=500.0,
            duration_days=30,
            current_balance=5000.0,
            entry_fee=99.0,
        )
        db.session.add(challenge)

    db.session.commit()


# Routes


# Health Check
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify(
        {
            "status": "healthy",
            "version": "1.0.0",
            "environment": "development",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
        }
    ), 200


# API Info
@app.route("/api", methods=["GET"])
@app.route("/api/v1", methods=["GET"])
def api_info():
    """API information endpoint."""
    return jsonify(
        {
            "name": "TradeSense AI API",
            "version": "v1",
            "description": "Professional prop trading platform API",
            "endpoints": {
                "auth": "/api/v1/auth",
                "portfolios": "/api/v1/portfolios",
                "trades": "/api/v1/trades",
                "challenges": "/api/v1/challenges",
            },
        }
    ), 200


# Authentication Routes
@app.route("/api/v1/auth/login", methods=["POST"])
def login():
    """User login endpoint."""
    try:
        schema = LoginSchema()
        data = schema.load(request.get_json() or {})

        user = User.query.filter_by(email=data["email"].lower()).first()

        if not user or not user.check_password(data["password"]):
            return jsonify(
                {
                    "error": {
                        "code": "INVALID_CREDENTIALS",
                        "message": "Invalid email or password",
                    }
                }
            ), 401

        if user.status != "active":
            return jsonify(
                {
                    "error": {
                        "code": "ACCOUNT_INACTIVE",
                        "message": f"Account is {user.status}",
                    }
                }
            ), 401

        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()

        # Create token (simplified - using email as token for demo)
        token = user.email
        active_tokens.add(token)

        return jsonify(
            {
                "message": "Login successful",
                "user": user.to_dict(),
                "tokens": {
                    "access_token": token,
                    "refresh_token": token,
                    "expires_in": 3600,
                },
            }
        ), 200

    except ValidationError as e:
        return jsonify(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid input data",
                    "details": e.messages,
                }
            }
        ), 400
    except Exception as e:
        return jsonify(
            {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An error occurred during login",
                }
            }
        ), 500


@app.route("/api/v1/auth/register", methods=["POST"])
def register():
    """User registration endpoint."""
    try:
        schema = RegisterSchema()
        data = schema.load(request.get_json() or {})

        # Check if passwords match
        if data["password"] != data["confirm_password"]:
            return jsonify(
                {
                    "error": {
                        "code": "PASSWORD_MISMATCH",
                        "message": "Passwords do not match",
                    }
                }
            ), 400

        # Check if user exists
        existing_user = User.query.filter_by(email=data["email"].lower()).first()
        if existing_user:
            return jsonify(
                {
                    "error": {
                        "code": "USER_EXISTS",
                        "message": "User with this email already exists",
                    }
                }
            ), 409

        # Create new user
        user = User(
            email=data["email"].lower(),
            first_name=data["first_name"],
            last_name=data["last_name"],
            experience_level=data.get("experience_level", "beginner"),
            country=data.get("country"),
        )
        user.set_password(data["password"])

        db.session.add(user)
        db.session.commit()

        # Create default portfolio
        portfolio = Portfolio(
            name=f"{user.first_name}'s Portfolio",
            description="Default trading portfolio",
            user_id=user.id,
            initial_balance=10000.0,
            current_balance=10000.0,
        )
        db.session.add(portfolio)
        db.session.commit()

        # Create token
        token = user.email
        active_tokens.add(token)

        return jsonify(
            {
                "message": "Registration successful",
                "user": user.to_dict(),
                "tokens": {
                    "access_token": token,
                    "refresh_token": token,
                    "expires_in": 3600,
                },
            }
        ), 201

    except ValidationError as e:
        return jsonify(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid input data",
                    "details": e.messages,
                }
            }
        ), 400
    except Exception as e:
        return jsonify(
            {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An error occurred during registration",
                }
            }
        ), 500


@app.route("/api/v1/auth/logout", methods=["POST"])
@token_required
def logout():
    """User logout endpoint."""
    token = (
        request.headers.get("Authorization", "").split(" ")[1]
        if request.headers.get("Authorization")
        else None
    )
    if token and token in active_tokens:
        active_tokens.remove(token)

    return jsonify({"message": "Logout successful"}), 200


@app.route("/api/v1/auth/me", methods=["GET"])
@token_required
def get_current_user():
    """Get current user information."""
    return jsonify({"user": g.current_user.to_dict()}), 200


# Portfolio Routes
@app.route("/api/v1/portfolios", methods=["GET"])
@token_required
def get_portfolios():
    """Get user portfolios."""
    portfolios = Portfolio.query.filter_by(user_id=g.current_user.id).all()
    return jsonify(
        {"portfolios": [p.to_dict() for p in portfolios], "total": len(portfolios)}
    ), 200


@app.route("/api/v1/portfolios/<int:portfolio_id>", methods=["GET"])
@token_required
def get_portfolio(portfolio_id):
    """Get specific portfolio."""
    portfolio = Portfolio.query.filter_by(
        id=portfolio_id, user_id=g.current_user.id
    ).first()
    if not portfolio:
        return jsonify(
            {"error": {"code": "NOT_FOUND", "message": "Portfolio not found"}}
        ), 404

    return jsonify({"portfolio": portfolio.to_dict()}), 200


# Trading Routes
@app.route("/api/v1/trades", methods=["GET"])
@token_required
def get_trades():
    """Get user trades."""
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 20, type=int)

    trades_query = Trade.query.filter_by(user_id=g.current_user.id)
    trades_paginated = trades_query.paginate(page=page, per_page=limit, error_out=False)

    return jsonify(
        {
            "trades": [t.to_dict() for t in trades_paginated.items],
            "pagination": {
                "page": page,
                "per_page": limit,
                "total": trades_paginated.total,
                "pages": trades_paginated.pages,
            },
        }
    ), 200


@app.route("/api/v1/trades", methods=["POST"])
@token_required
def create_trade():
    """Create new trade."""
    try:
        schema = TradeSchema()
        data = schema.load(request.get_json() or {})

        # Get user's first portfolio (simplified)
        portfolio = Portfolio.query.filter_by(
            user_id=g.current_user.id, is_active=True
        ).first()
        if not portfolio:
            return jsonify(
                {
                    "error": {
                        "code": "NO_PORTFOLIO",
                        "message": "No active portfolio found",
                    }
                }
            ), 400

        # Create trade with mock execution
        import random

        base_price = 1.1000 if "EUR" in data["symbol"] else 100.0
        executed_price = base_price + random.uniform(-0.01, 0.01) * base_price

        # Calculate mock P&L
        quantity = data["quantity"]
        if data["side"] == "sell":
            quantity = -quantity

        mock_pnl = random.uniform(-50, 100)

        trade = Trade(
            user_id=g.current_user.id,
            portfolio_id=portfolio.id,
            symbol=data["symbol"].upper(),
            side=data["side"],
            order_type=data["order_type"],
            quantity=abs(data["quantity"]),
            price=data.get("price"),
            executed_price=executed_price,
            pnl=mock_pnl,
            commission=abs(data["quantity"])
            * 0.0001
            * executed_price,  # Mock commission
            status="executed",
        )

        db.session.add(trade)

        # Update portfolio
        portfolio.current_balance += mock_pnl
        portfolio.total_pnl += mock_pnl
        portfolio.total_trades += 1
        if mock_pnl > 0:
            portfolio.winning_trades += 1

        db.session.commit()

        return jsonify(
            {"message": "Trade created successfully", "trade": trade.to_dict()}
        ), 201

    except ValidationError as e:
        return jsonify(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid trade data",
                    "details": e.messages,
                }
            }
        ), 400
    except Exception as e:
        return jsonify(
            {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An error occurred while creating trade",
                }
            }
        ), 500


# Challenge Routes
@app.route("/api/v1/challenges", methods=["GET"])
@token_required
def get_challenges():
    """Get challenges."""
    if g.current_user.role == "admin":
        challenges = Challenge.query.all()
    else:
        challenges = Challenge.query.filter_by(user_id=g.current_user.id).all()

    return jsonify(
        {"challenges": [c.to_dict() for c in challenges], "total": len(challenges)}
    ), 200


@app.route("/api/v1/challenges/<int:challenge_id>", methods=["GET"])
@token_required
def get_challenge(challenge_id):
    """Get specific challenge."""
    challenge = Challenge.query.get(challenge_id)
    if not challenge:
        return jsonify(
            {"error": {"code": "NOT_FOUND", "message": "Challenge not found"}}
        ), 404

    # Check access
    if g.current_user.role != "admin" and challenge.user_id != g.current_user.id:
        return jsonify(
            {"error": {"code": "FORBIDDEN", "message": "Access denied"}}
        ), 403

    return jsonify({"challenge": challenge.to_dict()}), 200


# Market Data Routes
@app.route("/api/v1/market/symbols", methods=["GET"])
@token_required
def get_symbols():
    """Get available trading symbols."""
    symbols = [
        {"symbol": "EURUSD", "name": "Euro / US Dollar", "type": "forex"},
        {"symbol": "GBPUSD", "name": "British Pound / US Dollar", "type": "forex"},
        {"symbol": "USDJPY", "name": "US Dollar / Japanese Yen", "type": "forex"},
        {"symbol": "AAPL", "name": "Apple Inc.", "type": "stock"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "type": "stock"},
        {"symbol": "MSFT", "name": "Microsoft Corporation", "type": "stock"},
        {"symbol": "TSLA", "name": "Tesla, Inc.", "type": "stock"},
    ]

    return jsonify({"symbols": symbols}), 200


@app.route("/api/v1/market/quote/<symbol>", methods=["GET"])
@token_required
def get_quote(symbol):
    """Get market quote for symbol."""
    import random

    # Mock market data
    base_price = 1.1000 if "USD" in symbol else 100.0
    price = base_price + random.uniform(-0.05, 0.05) * base_price

    quote = {
        "symbol": symbol.upper(),
        "price": round(price, 4),
        "bid": round(price - 0.0002, 4),
        "ask": round(price + 0.0002, 4),
        "change": round(random.uniform(-2, 2), 2),
        "change_percent": round(random.uniform(-2, 2), 2),
        "volume": random.randint(1000000, 10000000),
        "timestamp": datetime.utcnow().isoformat(),
    }

    return jsonify({"quote": quote}), 200


# Analytics Routes
@app.route("/api/v1/analytics/performance", methods=["GET"])
@token_required
def get_performance():
    """Get performance analytics."""
    portfolio_id = request.args.get("portfolio_id")

    if portfolio_id:
        portfolio = Portfolio.query.filter_by(
            id=portfolio_id, user_id=g.current_user.id
        ).first()
        if not portfolio:
            return jsonify(
                {"error": {"code": "NOT_FOUND", "message": "Portfolio not found"}}
            ), 404

        portfolios = [portfolio]
    else:
        portfolios = Portfolio.query.filter_by(user_id=g.current_user.id).all()

    total_balance = sum(p.current_balance for p in portfolios)
    total_pnl = sum(p.total_pnl for p in portfolios)
    total_trades = sum(p.total_trades for p in portfolios)
    total_winning = sum(p.winning_trades for p in portfolios)

    performance = {
        "total_balance": total_balance,
        "total_pnl": total_pnl,
        "total_trades": total_trades,
        "win_rate": (total_winning / total_trades * 100) if total_trades > 0 else 0,
        "return_percentage": (total_pnl / 10000.0 * 100) if total_pnl != 0 else 0,
        "portfolios_count": len(portfolios),
    }

    return jsonify({"performance": performance}), 200


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify(
        {
            "error": {
                "code": "NOT_FOUND",
                "message": "Endpoint not found",
                "path": request.path,
            }
        }
    ), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify(
        {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred",
            }
        }
    ), 500


# Initialize database and create sample data
with app.app_context():
    db.create_all()
    create_sample_data()
    print("🗄️ Database initialized with sample data")
    print("🔑 Demo Credentials:")
    print("   - Admin: admin@tradesense.ai / admin123456")
    print("   - Demo Trader: demo.trader@tradesense.ai / demo123456")


if __name__ == "__main__":
    print("🚀 Starting TradeSense AI - Simplified Backend")
    print("🌐 Server running on: http://localhost:5000")
    print("📚 API Documentation available at: http://localhost:5000/api")
