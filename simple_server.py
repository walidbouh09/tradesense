#!/usr/bin/env python3
"""
TradeSense AI - Ultra-Simple Backend Server
A minimal Flask server that works immediately without complex dependencies.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

try:
    from flask import Flask, g, jsonify, request
    from flask_cors import CORS
except ImportError:
    print("Installing Flask...")
    os.system("pip install flask flask-cors")
    from flask import Flask, g, jsonify, request
    from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins="*")

# Simple in-memory storage for demo
users = {
    "admin@tradesense.ai": {
        "id": "1",
        "email": "admin@tradesense.ai",
        "password": "admin123456",
        "full_name": "Admin TradeSense",
        "first_name": "Admin",
        "last_name": "TradeSense",
        "role": "admin",
        "status": "active",
        "is_verified": True,
        "experience_level": "advanced",
        "country": "USA",
        "created_at": datetime.now().isoformat(),
    },
    "demo.trader@tradesense.ai": {
        "id": "2",
        "email": "demo.trader@tradesense.ai",
        "password": "demo123456",
        "full_name": "Demo Trader",
        "first_name": "Demo",
        "last_name": "Trader",
        "role": "trader",
        "status": "active",
        "is_verified": True,
        "experience_level": "intermediate",
        "country": "USA",
        "created_at": datetime.now().isoformat(),
    },
}

# Simple token storage
active_tokens = set()


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if token:
            token = token.replace("Bearer ", "")

        if not token or token not in active_tokens:
            return jsonify(
                {"error": {"code": "UNAUTHORIZED", "message": "Token required"}}
            ), 401

        # Find user by token (simplified - using email as token)
        user = None
        for email, user_data in users.items():
            if email == token:
                user = user_data
                break

        if not user:
            return jsonify(
                {"error": {"code": "USER_NOT_FOUND", "message": "User not found"}}
            ), 401

        g.current_user = user
        return f(*args, **kwargs)

    return decorated


# Health check
@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "healthy",
            "version": "1.0.0",
            "environment": "development",
            "database": "connected",
            "timestamp": datetime.now().isoformat(),
        }
    )


# API info
@app.route("/api", methods=["GET"])
def api_info():
    return jsonify(
        {
            "name": "TradeSense AI API",
            "version": "v1",
            "description": "Professional prop trading platform API",
            "status": "operational",
            "endpoints": {
                "health": "/health",
                "auth": "/api/v1/auth/*",
                "portfolios": "/api/v1/portfolios",
                "trades": "/api/v1/trades",
                "market": "/api/v1/market/*",
            },
        }
    )


# Auth endpoints
@app.route("/api/v1/auth/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {"error": {"code": "INVALID_INPUT", "message": "JSON data required"}}
            ), 400

        email = data.get("email", "").lower()
        password = data.get("password", "")

        if not email or not password:
            return jsonify(
                {
                    "error": {
                        "code": "MISSING_FIELDS",
                        "message": "Email and password required",
                    }
                }
            ), 400

        # Check user exists
        if email not in users:
            return jsonify(
                {
                    "error": {
                        "code": "INVALID_CREDENTIALS",
                        "message": "Invalid email or password",
                    }
                }
            ), 401

        user = users[email]
        if user["password"] != password:
            return jsonify(
                {
                    "error": {
                        "code": "INVALID_CREDENTIALS",
                        "message": "Invalid email or password",
                    }
                }
            ), 401

        # Create token (simplified - use email as token)
        token = email
        active_tokens.add(token)

        return jsonify(
            {
                "message": "Login successful",
                "user": {k: v for k, v in user.items() if k != "password"},
                "tokens": {
                    "access_token": token,
                    "refresh_token": token,
                    "expires_in": 3600,
                },
            }
        )

    except Exception as e:
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": str(e)}}), 500


@app.route("/api/v1/auth/me", methods=["GET"])
@token_required
def get_current_user():
    user = g.current_user
    return jsonify({"user": {k: v for k, v in user.items() if k != "password"}})


@app.route("/api/v1/auth/logout", methods=["POST"])
@token_required
def logout():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token in active_tokens:
        active_tokens.remove(token)
    return jsonify({"message": "Logout successful"})


# Portfolios
@app.route("/api/v1/portfolios", methods=["GET"])
@token_required
def get_portfolios():
    return jsonify(
        {
            "portfolios": [
                {
                    "id": "1",
                    "name": f"{g.current_user['first_name']}'s Portfolio",
                    "description": "Demo trading portfolio",
                    "current_balance": 10000.00,
                    "total_pnl": 250.50,
                    "total_trades": 15,
                    "winning_trades": 9,
                    "win_rate": 60.0,
                    "return_percentage": 2.5,
                    "is_active": True,
                    "is_demo": True,
                    "created_at": datetime.now().isoformat(),
                }
            ],
            "total": 1,
        }
    )


# Trades
@app.route("/api/v1/trades", methods=["GET"])
@token_required
def get_trades():
    return jsonify(
        {
            "trades": [
                {
                    "id": "1",
                    "symbol": "EURUSD",
                    "side": "buy",
                    "quantity": 1000,
                    "executed_price": 1.0850,
                    "pnl": 25.50,
                    "status": "executed",
                    "created_at": datetime.now().isoformat(),
                }
            ],
            "pagination": {"page": 1, "per_page": 20, "total": 1, "pages": 1},
        }
    )


@app.route("/api/v1/trades", methods=["POST"])
@token_required
def create_trade():
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {"error": {"code": "INVALID_INPUT", "message": "JSON data required"}}
            ), 400

        # Mock trade creation
        import random

        pnl = round(random.uniform(-50, 100), 2)

        trade = {
            "id": str(random.randint(1000, 9999)),
            "symbol": data.get("symbol", "EURUSD"),
            "side": data.get("side", "buy"),
            "quantity": data.get("quantity", 1000),
            "executed_price": round(1.0800 + random.uniform(-0.01, 0.01), 4),
            "pnl": pnl,
            "status": "executed",
            "created_at": datetime.now().isoformat(),
        }

        return jsonify({"message": "Trade executed successfully", "trade": trade})

    except Exception as e:
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": str(e)}}), 500


# Market data
@app.route("/api/v1/market/symbols", methods=["GET"])
@token_required
def get_symbols():
    return jsonify(
        {
            "symbols": [
                {"symbol": "EURUSD", "name": "Euro / US Dollar", "type": "forex"},
                {
                    "symbol": "GBPUSD",
                    "name": "British Pound / US Dollar",
                    "type": "forex",
                },
                {
                    "symbol": "USDJPY",
                    "name": "US Dollar / Japanese Yen",
                    "type": "forex",
                },
                {"symbol": "AAPL", "name": "Apple Inc.", "type": "stock"},
                {"symbol": "GOOGL", "name": "Alphabet Inc.", "type": "stock"},
                {"symbol": "MSFT", "name": "Microsoft Corporation", "type": "stock"},
            ]
        }
    )


@app.route("/api/v1/market/quote/<symbol>", methods=["GET"])
@token_required
def get_quote(symbol):
    import random

    base_price = 1.0850 if "USD" in symbol else 150.00
    price = round(base_price + random.uniform(-0.05, 0.05) * base_price, 4)

    return jsonify(
        {
            "quote": {
                "symbol": symbol.upper(),
                "price": price,
                "bid": round(price - 0.0002, 4),
                "ask": round(price + 0.0002, 4),
                "change": round(random.uniform(-2, 2), 2),
                "change_percent": round(random.uniform(-2, 2), 2),
                "timestamp": datetime.now().isoformat(),
            }
        }
    )


# Challenges
@app.route("/api/v1/challenges", methods=["GET"])
@token_required
def get_challenges():
    return jsonify(
        {
            "challenges": [
                {
                    "id": "1",
                    "name": "Beginner Trading Challenge",
                    "description": "Perfect for new traders",
                    "initial_balance": 5000.00,
                    "target_profit": 400.00,
                    "current_pnl": 125.50,
                    "status": "active",
                    "progress_percentage": 31.4,
                    "duration_days": 30,
                    "created_at": datetime.now().isoformat(),
                }
            ],
            "total": 1,
        }
    )


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


if __name__ == "__main__":
    print("🚀 TradeSense AI - Ultra-Simple Backend")
    print("=" * 50)
    print("🌐 Server starting on: http://localhost:5000")
    print("📊 Health check: http://localhost:5000/health")
    print("📚 API info: http://localhost:5000/api")
    print("🔑 Demo Credentials:")
    print("   - Demo Trader: demo.trader@tradesense.ai / demo123456")
    print("   - Admin: admin@tradesense.ai / admin123456")
    print("🛑 Press Ctrl+C to stop")
    print("=" * 50)

    try:
        app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
