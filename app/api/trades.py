"""
Trading API Endpoints

Handle trade execution and real-time equity updates.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from flask import current_app, jsonify, request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.market_data import market_data
from app.order_engine import OrderStatus, OrderType, order_engine
from app.portfolio_manager import portfolio_manager

from . import api_bp


def get_db_session():
    """Get database session."""
    database_url = current_app.config.get(
        "DATABASE_URL",
        "postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense",
    )
    engine = create_engine(database_url, echo=False)
    return Session(engine)


@api_bp.route("/trades", methods=["POST"])
def execute_trade():
    """
    Execute a trade for a challenge.

    Updates equity, checks rules, and emits real-time events.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No trade data provided"}), 400

        required_fields = ["challenge_id", "symbol", "side", "quantity", "price"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"{field} is required"}), 400

        challenge_id = data["challenge_id"]
        symbol = data["symbol"]
        side = data["side"].upper()
        quantity = Decimal(str(data["quantity"]))
        price = Decimal(str(data["price"]))

        if side not in ["BUY", "SELL"]:
            return jsonify({"error": "Side must be BUY or SELL"}), 400

        if quantity <= 0 or price <= 0:
            return jsonify({"error": "Quantity and price must be positive"}), 400

        session = get_db_session()

        # Get current challenge state with FOR UPDATE for concurrency
        # Include daily fields so we can enforce daily loss rules deterministically
        challenge = session.execute(
            text("""
            SELECT
                id,
                status,
                initial_balance,
                current_equity,
                max_equity_ever,
                daily_start_equity,
                daily_max_equity,
                daily_min_equity,
                current_date_value
            FROM challenges
            WHERE id = :challenge_id
            FOR UPDATE
        """),
            {"challenge_id": challenge_id},
        ).fetchone()

        if not challenge:
            return jsonify({"error": "Challenge not found"}), 404

        # If challenge is in a terminal state (explicit check for FAILED or PASSED/FUNDED), refuse
        if str(challenge.status).upper() in ["FAILED", "PASSED", "FUNDED"]:
            return jsonify(
                {
                    "error": "Challenge in terminal state, cannot execute trades",
                    "challenge_status": challenge.status,
                    "code": "CHALLENGE_TERMINAL",
                }
            ), 403

        # Allow first trade to activate a PENDING challenge
        if challenge.status not in ["PENDING", "ACTIVE"]:
            return jsonify(
                {"error": f"Challenge is {challenge.status}, cannot execute trades"}
            ), 400

        # Use deterministic rule parameters (as per requirements)
        max_daily_loss_pct = Decimal("0.05")  # 5%
        max_total_loss_pct = Decimal("0.10")  # 10%
        profit_target_pct = Decimal("0.10")  # 10%

        # Get current market price for the symbol (deterministic: fail if unavailable)
        current_price, _ = market_data.get_stock_price(symbol)
        if current_price is None:
            return jsonify(
                {"error": "Current market price unavailable for symbol"}
            ), 503

        # Calculate PnL based on market movement
        if side == "BUY":
            # For buy trades, PnL = (current_price - entry_price) * quantity
            realized_pnl = (current_price - price) * quantity
        else:  # SELL
            # For sell trades, PnL = (entry_price - current_price) * quantity
            realized_pnl = (price - current_price) * quantity

        # Recalculate equity
        current_equity = Decimal(str(challenge.current_equity))
        initial_balance = Decimal(str(challenge.initial_balance))
        new_equity = current_equity + realized_pnl

        # Ensure equity never goes below zero
        if new_equity < 0:
            new_equity = Decimal("0")

        # Handle daily reset (UTC-based) for daily loss tracking
        now_utc = datetime.now(timezone.utc)
        current_trading_date = challenge.current_date_value

        if current_trading_date is None or current_trading_date != now_utc.date():
            # New trading day: reset daily metrics from pre-trade equity
            daily_start_equity = current_equity
            daily_max_equity = current_equity
            daily_min_equity = current_equity
            current_trading_date = now_utc.date()
        else:
            # Continue same day
            daily_start_equity = Decimal(str(challenge.daily_start_equity))
            daily_max_equity = Decimal(str(challenge.daily_max_equity))
            daily_min_equity = Decimal(str(challenge.daily_min_equity))

        # Update daily high/low with new equity
        daily_max_equity = max(daily_max_equity, new_equity)
        daily_min_equity = min(daily_min_equity, new_equity)

        # Update max equity ever
        max_equity_ever = Decimal(str(challenge.max_equity_ever))
        new_max_equity = max(max_equity_ever, new_equity)

        # Compute risk metrics (loss and profit percentages)
        # Total loss from initial balance
        total_loss_pct = (initial_balance - new_equity) / initial_balance

        # Daily loss from daily_start_equity (guard against divide-by-zero)
        if daily_start_equity > 0:
            daily_loss_pct = (daily_start_equity - new_equity) / daily_start_equity
        else:
            daily_loss_pct = Decimal("0")

        # Profit vs initial balance
        profit_pct = (new_equity - initial_balance) / initial_balance

        # Determine new status based on rules
        new_status = "ACTIVE"
        failure_reason = None

        if daily_loss_pct >= max_daily_loss_pct:
            new_status = "FAILED"
            failure_reason = "MAX_DAILY_LOSS"
        elif total_loss_pct >= max_total_loss_pct:
            new_status = "FAILED"
            failure_reason = "MAX_TOTAL_LOSS"
        elif profit_pct >= profit_target_pct:
            # Map business concept \"PASSED\" to existing enum \"FUNDED\"
            new_status = "FUNDED"

        # Create trade record
        trade_id = str(uuid4())
        executed_at = now_utc

        session.execute(
            text("""
            INSERT INTO trades (
                id, challenge_id, symbol, side, quantity, price, realized_pnl, executed_at
            ) VALUES (
                :id, :challenge_id, :symbol, :side, :quantity, :price, :pnl, :executed_at
            )
        """),
            {
                "id": trade_id,
                "challenge_id": challenge_id,
                "symbol": symbol,
                "side": side,
                "quantity": float(quantity),
                "price": float(price),
                "pnl": float(realized_pnl),
                "executed_at": executed_at,
            },
        )

        # Update challenge
        ended_at = executed_at if new_status in ["FAILED", "FUNDED"] else None
        started_at = executed_at if challenge.status == "PENDING" else None

        session.execute(
            text("""
            UPDATE challenges
            SET current_equity     = :equity,
                max_equity_ever    = :max_equity,
                daily_start_equity = :daily_start_equity,
                daily_max_equity   = :daily_max_equity,
                daily_min_equity   = :daily_min_equity,
                current_date_value = :current_date,
                status             = :status,
                failure_reason     = :failure_reason,
                started_at         = COALESCE(started_at, :started_at),
                funded_at          = CASE WHEN :status = 'FUNDED' AND funded_at IS NULL THEN :ended_at ELSE funded_at END,
                ended_at           = CASE WHEN :ended_at IS NOT NULL THEN :ended_at ELSE ended_at END,
                last_trade_at      = :last_trade_at,
                total_trades       = total_trades + 1,
                updated_at         = :updated_at
            WHERE id = :challenge_id
        """),
            {
                "equity": float(new_equity),
                "max_equity": float(new_max_equity),
                "daily_start_equity": float(daily_start_equity),
                "daily_max_equity": float(daily_max_equity),
                "daily_min_equity": float(daily_min_equity),
                "current_date": current_trading_date,
                "status": new_status,
                "failure_reason": failure_reason,
                "started_at": started_at,
                "ended_at": ended_at,
                "last_trade_at": executed_at,
                "updated_at": executed_at,
                "challenge_id": challenge_id,
            },
        )

        # Create challenge event for audit trail
        event_id = str(uuid4())
        session.execute(
            text("""
            INSERT INTO challenge_events (
                id, challenge_id, event_type, event_data, occurred_at
            ) VALUES (
                :id, :challenge_id, 'TRADE_EXECUTED',
                :event_data, :occurred_at
            )
        """),
            {
                "id": event_id,
                "challenge_id": challenge_id,
                "event_data": {
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "side": side,
                    "quantity": float(quantity),
                    "price": float(price),
                    "pnl": float(realized_pnl),
                    "new_equity": float(new_equity),
                },
                "occurred_at": executed_at,
            },
        )

        session.commit()

        # Emit real-time events (would be handled by WebSocket in production)
        # For now, just log the events
        current_app.logger.info(
            f"Trade executed: {trade_id} for challenge {challenge_id}"
        )
        current_app.logger.info(
            f"Equity updated: {new_equity} (was {challenge.current_equity})"
        )

        return jsonify(
            {
                "trade_id": trade_id,
                "challenge_id": challenge_id,
                "symbol": symbol,
                "side": side,
                "quantity": float(quantity),
                "price": float(price),
                "realized_pnl": float(realized_pnl),
                "executed_at": executed_at.isoformat(),
                "new_equity": float(new_equity),
                "status": new_status,
            }
        ), 201

    except Exception as e:
        current_app.logger.error(f"Trade execution error: {e}")
        session.rollback()
        return jsonify({"error": "Trade execution failed"}), 500
    finally:
        session.close()


@api_bp.route("/market/prices", methods=["GET"])
def get_market_prices():
    """
    Get current market prices for symbols.

    Professional API endpoint with comprehensive price data.
    Accepts comma-separated list of symbols.

    Query Parameters:
    - symbols: Comma-separated list of stock symbols (e.g., "AAPL,BCP.MA,MSFT")

    Returns:
    - current_price: Current trading price
    - previous_close: Previous trading day's close
    - change: Price change from previous close
    - change_percent: Percentage change
    - source: Data source (yahoo, casablanca, mock)
    - last_updated: Timestamp of data
    """
    try:
        symbols_param = request.args.get("symbols", "")
        if not symbols_param:
            return jsonify(
                {
                    "error": "Symbols parameter required",
                    "example": "/api/market/prices?symbols=AAPL,BCP.MA,MSFT",
                }
            ), 400

        symbols = [s.strip().upper() for s in symbols_param.split(",") if s.strip()]
        if not symbols:
            return jsonify({"error": "No valid symbols provided"}), 400

        if len(symbols) > 10:
            return jsonify({"error": "Maximum 10 symbols per request"}), 400

        prices = market_data.get_multiple_prices(symbols)
        result = {}
        now = datetime.now(timezone.utc).isoformat()

        for symbol in symbols:
            current_price, previous_close = prices.get(symbol, (None, None))

            if current_price is not None:
                change = float(current_price - previous_close) if previous_close else 0
                change_percent = (
                    float((change / float(previous_close)) * 100)
                    if previous_close and previous_close != 0
                    else 0
                )

                # Determine data source
                if symbol.endswith(".MA"):
                    source = "casablanca"
                else:
                    source = "yahoo"

                result[symbol] = {
                    "current_price": float(current_price),
                    "previous_close": float(previous_close) if previous_close else None,
                    "change": round(change, 2),
                    "change_percent": round(change_percent, 2),
                    "source": source,
                    "last_updated": now,
                    "currency": "MAD" if symbol.endswith(".MA") else "USD",
                }
            else:
                result[symbol] = {"error": "Price not available", "last_updated": now}

        return jsonify(
            {
                "prices": result,
                "count": len([p for p in result.values() if "current_price" in p]),
                "timestamp": now,
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Market prices error: {e}")
        return jsonify({"error": "Failed to get market prices"}), 500


@api_bp.route("/market/test-scraping", methods=["GET"])
def test_market_scraping():
    """
    Test endpoint to verify market data scraping is working.

    Tests both Yahoo Finance and Casablanca scraping.
    """
    try:
        test_results = {}

        # Test Yahoo Finance
        print("Testing Yahoo Finance...")
        yahoo_price = market_data._get_yahoo_price("AAPL")
        test_results["yahoo_finance"] = {
            "symbol": "AAPL",
            "current_price": float(yahoo_price[0]) if yahoo_price[0] else None,
            "previous_close": float(yahoo_price[1]) if yahoo_price[1] else None,
            "success": yahoo_price[0] is not None,
        }

        # Test Casablanca scraping
        print("Testing Casablanca scraping...")
        casa_price = market_data._get_casablanca_price_real("BCP.MA")
        test_results["casablanca_scraping"] = {
            "symbol": "BCP.MA",
            "current_price": float(casa_price[0]) if casa_price[0] else None,
            "previous_close": float(casa_price[1]) if casa_price[1] else None,
            "success": casa_price[0] is not None,
        }

        # Test fallback data
        casa_mock = market_data._get_casablanca_price_mock("BCP.MA")
        test_results["casablanca_mock"] = {
            "symbol": "BCP.MA",
            "current_price": float(casa_mock[0]) if casa_mock[0] else None,
            "previous_close": float(casa_mock[1]) if casa_mock[1] else None,
            "success": casa_mock[0] is not None,
        }

        return jsonify(
            {
                "message": "Market data scraping test completed",
                "tests": test_results,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Market scraping test error: {e}")
        return jsonify({"error": "Failed to test market scraping"}), 500


@api_bp.route("/orders", methods=["POST"])
def create_order():
    """
    Create an advanced order.

    Supports market, limit, stop-loss, take-profit, and trailing stop orders.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No order data provided"}), 400

        required_fields = ["challenge_id", "symbol", "side", "quantity"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"{field} is required"}), 400

        # Extract order parameters
        challenge_id = data["challenge_id"]
        symbol = data["symbol"].upper()
        side = data["side"].upper()
        quantity = Decimal(str(data["quantity"]))

        order_type = data.get("order_type", "MARKET").upper()
        limit_price = data.get("limit_price")
        stop_price = data.get("stop_price")
        take_profit_price = data.get("take_profit_price")
        trailing_stop_percent = data.get("trailing_stop_percent")
        time_in_force = data.get("time_in_force", "GTC")

        # Convert prices to Decimal if provided
        if limit_price:
            limit_price = Decimal(str(limit_price))
        if stop_price:
            stop_price = Decimal(str(stop_price))
        if take_profit_price:
            take_profit_price = Decimal(str(take_profit_price))
        if trailing_stop_percent:
            trailing_stop_percent = Decimal(str(trailing_stop_percent))

        # Validate challenge exists and is active
        session = get_db_session()
        challenge = session.execute(
            text("""
            SELECT id, status FROM challenges
            WHERE id = :challenge_id
        """),
            {"challenge_id": challenge_id},
        ).fetchone()

        if not challenge:
            return jsonify({"error": "Challenge not found"}), 404

        # Refuse order creation if challenge is in terminal state (FAILED or PASSED/FUNDED)
        if str(challenge.status).upper() in ["FAILED", "PASSED", "FUNDED"]:
            return jsonify(
                {
                    "error": "Challenge in terminal state, cannot create orders",
                    "challenge_status": challenge.status,
                    "code": "CHALLENGE_TERMINAL",
                }
            ), 403

        if challenge.status != "ACTIVE":
            return jsonify(
                {"error": f"Challenge is {challenge.status}, cannot create orders"}
            ), 400

        # Create the order using the order engine
        order = order_engine.create_order(
            challenge_id=challenge_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            take_profit_price=take_profit_price,
            trailing_stop_percent=trailing_stop_percent,
            time_in_force=time_in_force,
        )

        # Save order to database
        session.execute(
            text("""
            INSERT INTO orders (
                id, challenge_id, symbol, side, quantity, order_type,
                limit_price, stop_price, take_profit_price, trailing_stop_percent,
                status, time_in_force, filled_quantity, remaining_quantity,
                created_at, updated_at, metadata
            ) VALUES (
                :id, :challenge_id, :symbol, :side, :quantity, :order_type,
                :limit_price, :stop_price, :take_profit_price, :trailing_stop_percent,
                :status, :time_in_force, :filled_quantity, :remaining_quantity,
                :created_at, :updated_at, :metadata
            )
        """),
            {
                "id": order.order_id,
                "challenge_id": challenge_id,
                "symbol": symbol,
                "side": side,
                "quantity": float(quantity),
                "order_type": order_type,
                "limit_price": float(limit_price) if limit_price else None,
                "stop_price": float(stop_price) if stop_price else None,
                "take_profit_price": float(take_profit_price)
                if take_profit_price
                else None,
                "trailing_stop_percent": float(trailing_stop_percent)
                if trailing_stop_percent
                else None,
                "status": order.status.value,
                "time_in_force": time_in_force,
                "filled_quantity": float(order.filled_quantity),
                "remaining_quantity": float(order.remaining_quantity),
                "created_at": order.created_at,
                "updated_at": order.updated_at,
                "metadata": order.metadata,
            },
        )

        # If order was executed immediately (market order), create trade record
        if order.status == OrderStatus.FILLED:
            execution_price = order.average_fill_price
            realized_pnl = Decimal("0")  # Market orders have no realized PnL yet

            session.execute(
                text("""
                INSERT INTO trades (
                    id, challenge_id, order_id, symbol, side, quantity, price,
                    realized_pnl, executed_at, commission
                ) VALUES (
                    :id, :challenge_id, :order_id, :symbol, :side, :quantity, :price,
                    :pnl, :executed_at, :commission
                )
            """),
                {
                    "id": str(uuid.uuid4()),
                    "challenge_id": challenge_id,
                    "order_id": order.order_id,
                    "symbol": symbol,
                    "side": side,
                    "quantity": float(quantity),
                    "price": float(execution_price),
                    "pnl": float(realized_pnl),
                    "executed_at": datetime.now(timezone.utc),
                    "commission": 0.0,
                },
            )

        session.commit()

        return jsonify(
            {
                "order_id": order.order_id,
                "challenge_id": challenge_id,
                "symbol": symbol,
                "side": side,
                "quantity": float(quantity),
                "order_type": order_type,
                "status": order.status.value,
                "limit_price": float(limit_price) if limit_price else None,
                "stop_price": float(stop_price) if stop_price else None,
                "take_profit_price": float(take_profit_price)
                if take_profit_price
                else None,
                "trailing_stop_percent": float(trailing_stop_percent)
                if trailing_stop_percent
                else None,
                "filled_quantity": float(order.filled_quantity),
                "remaining_quantity": float(order.remaining_quantity),
                "average_fill_price": float(order.average_fill_price)
                if order.average_fill_price
                else None,
                "created_at": order.created_at.isoformat(),
            }
        ), 201

    except Exception as e:
        current_app.logger.error(f"Order creation error: {e}")
        session.rollback()
        return jsonify({"error": "Failed to create order"}), 500
    finally:
        session.close()


@api_bp.route("/orders", methods=["GET"])
def get_orders():
    """
    Get orders for a challenge.

    Query parameter: challenge_id (required)
    """
    try:
        challenge_id = request.args.get("challenge_id")
        if not challenge_id:
            return jsonify({"error": "challenge_id parameter required"}), 400

        session = get_db_session()

        orders = session.execute(
            text("""
            SELECT
                id, symbol, side, quantity, order_type, status, limit_price,
                stop_price, take_profit_price, trailing_stop_percent,
                filled_quantity, remaining_quantity, average_fill_price,
                created_at, updated_at
            FROM orders
            WHERE challenge_id = :challenge_id
            ORDER BY created_at DESC
        """),
            {"challenge_id": challenge_id},
        ).fetchall()

        order_list = []
        for order in orders:
            order_list.append(
                {
                    "order_id": str(order.id),
                    "symbol": order.symbol,
                    "side": order.side,
                    "quantity": float(order.quantity),
                    "order_type": order.order_type,
                    "status": order.status,
                    "limit_price": float(order.limit_price)
                    if order.limit_price
                    else None,
                    "stop_price": float(order.stop_price) if order.stop_price else None,
                    "take_profit_price": float(order.take_profit_price)
                    if order.take_profit_price
                    else None,
                    "trailing_stop_percent": float(order.trailing_stop_percent)
                    if order.trailing_stop_percent
                    else None,
                    "filled_quantity": float(order.filled_quantity or 0),
                    "remaining_quantity": float(order.remaining_quantity or 0),
                    "average_fill_price": float(order.average_fill_price)
                    if order.average_fill_price
                    else None,
                    "created_at": order.created_at.isoformat(),
                    "updated_at": order.updated_at.isoformat(),
                }
            )

        return jsonify({"orders": order_list, "count": len(order_list)}), 200

    except Exception as e:
        current_app.logger.error(f"Get orders error: {e}")
        return jsonify({"error": "Failed to get orders"}), 500
    finally:
        session.close()


@api_bp.route("/orders/<order_id>", methods=["DELETE"])
def cancel_order(order_id):
    """
    Cancel an active order.
    """
    try:
        session = get_db_session()

        # Get order from database
        order = session.execute(
            text("""
            SELECT id, challenge_id, status FROM orders
            WHERE id = :order_id
        """),
            {"order_id": order_id},
        ).fetchone()

        if not order:
            return jsonify({"error": "Order not found"}), 404

        if order.status not in ["PENDING", "OPEN"]:
            return jsonify(
                {"error": f"Cannot cancel order with status {order.status}"}
            ), 400

        # Cancel the order
        cancelled_order = order_engine.cancel_order(order_id)

        if cancelled_order:
            # Update database
            session.execute(
                text("""
                UPDATE orders
                SET status = 'CANCELLED', updated_at = :updated_at
                WHERE id = :order_id
            """),
                {"order_id": order_id, "updated_at": datetime.now(timezone.utc)},
            )

            session.commit()

            return jsonify(
                {
                    "order_id": order_id,
                    "status": "CANCELLED",
                    "cancelled_at": datetime.now(timezone.utc).isoformat(),
                }
            ), 200
        else:
            return jsonify({"error": "Failed to cancel order"}), 500

    except Exception as e:
        current_app.logger.error(f"Cancel order error: {e}")
        return jsonify({"error": "Failed to cancel order"}), 500
    finally:
        session.close()


@api_bp.route("/orders/bracket", methods=["POST"])
def create_bracket_order():
    """
    Create a bracket order (entry + stop loss + take profit).
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No bracket order data provided"}), 400

        required_fields = ["challenge_id", "symbol", "side", "quantity"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"{field} is required"}), 400

        challenge_id = data["challenge_id"]
        symbol = data["symbol"].upper()
        side = data["side"].upper()
        quantity = Decimal(str(data["quantity"]))

        entry_price = data.get("entry_price")
        stop_loss_percent = data.get("stop_loss_percent")
        take_profit_percent = data.get("take_profit_percent")

        if entry_price:
            entry_price = Decimal(str(entry_price))
        if stop_loss_percent:
            stop_loss_percent = Decimal(str(stop_loss_percent))
        if take_profit_percent:
            take_profit_percent = Decimal(str(take_profit_percent))

        # Validate challenge exists and is active
        session = get_db_session()
        challenge = session.execute(
            text("""
            SELECT id, status FROM challenges
            WHERE id = :challenge_id
        """),
            {"challenge_id": challenge_id},
        ).fetchone()

        if not challenge:
            return jsonify({"error": "Challenge not found"}), 404

        if challenge.status != "ACTIVE":
            return jsonify(
                {"error": f"Challenge is {challenge.status}, cannot create orders"}
            ), 400

        # Create bracket order
        orders = order_engine.create_bracket_order(
            challenge_id=challenge_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss_percent=stop_loss_percent,
            take_profit_percent=take_profit_percent,
        )

        # Save orders to database
        created_orders = []
        for order in orders:
            session.execute(
                text("""
                INSERT INTO orders (
                    id, challenge_id, symbol, side, quantity, order_type,
                    limit_price, stop_price, take_profit_price, trailing_stop_percent,
                    status, time_in_force, filled_quantity, remaining_quantity,
                    parent_order_id, linked_order_id, created_at, updated_at, metadata
                ) VALUES (
                    :id, :challenge_id, :symbol, :side, :quantity, :order_type,
                    :limit_price, :stop_price, :take_profit_price, :trailing_stop_percent,
                    :status, :time_in_force, :filled_quantity, :remaining_quantity,
                    :parent_order_id, :linked_order_id, :created_at, :updated_at, :metadata
                )
            """),
                {
                    "id": order.order_id,
                    "challenge_id": challenge_id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "quantity": float(order.quantity),
                    "order_type": order.order_type.value,
                    "limit_price": float(order.limit_price)
                    if order.limit_price
                    else None,
                    "stop_price": float(order.stop_price) if order.stop_price else None,
                    "take_profit_price": float(order.take_profit_price)
                    if order.take_profit_price
                    else None,
                    "trailing_stop_percent": float(order.trailing_stop_percent)
                    if order.trailing_stop_percent
                    else None,
                    "status": order.status.value,
                    "time_in_force": order.time_in_force,
                    "filled_quantity": float(order.filled_quantity),
                    "remaining_quantity": float(order.remaining_quantity),
                    "parent_order_id": order.parent_order_id,
                    "linked_order_id": order.linked_order_id,
                    "created_at": order.created_at,
                    "updated_at": order.updated_at,
                    "metadata": order.metadata,
                },
            )

            created_orders.append(
                {
                    "order_id": order.order_id,
                    "order_type": order.order_type.value,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "quantity": float(order.quantity),
                    "status": order.status.value,
                    "limit_price": float(order.limit_price)
                    if order.limit_price
                    else None,
                    "stop_price": float(order.stop_price) if order.stop_price else None,
                    "take_profit_price": float(order.take_profit_price)
                    if order.take_profit_price
                    else None,
                    "trailing_stop_percent": float(order.trailing_stop_percent)
                    if order.trailing_stop_percent
                    else None,
                }
            )

        session.commit()

        return jsonify(
            {
                "bracket_order": {
                    "challenge_id": challenge_id,
                    "symbol": symbol,
                    "side": side,
                    "quantity": float(quantity),
                    "orders": created_orders,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            }
        ), 201

    except Exception as e:
        current_app.logger.error(f"Bracket order creation error: {e}")
        session.rollback()
        return jsonify({"error": "Failed to create bracket order"}), 500
    finally:
        session.close()


@api_bp.route("/orders/monitor", methods=["POST"])
def monitor_orders():
    """
    Monitor active orders and execute triggered orders.

    This endpoint should be called periodically to check for order triggers.
    """
    try:
        # Monitor all active orders
        triggered_orders = order_engine.monitor_orders()

        session = get_db_session()

        # Update triggered orders in database
        for execution in triggered_orders:
            order_id = execution["order_id"]

            # Update order status
            session.execute(
                text("""
                UPDATE orders
                SET status = :status, filled_quantity = :filled_quantity,
                    remaining_quantity = :remaining_quantity,
                    average_fill_price = :avg_price, updated_at = :updated_at
                WHERE id = :order_id
            """),
                {
                    "order_id": order_id,
                    "status": "FILLED",
                    "filled_quantity": execution["fill_quantity"],
                    "remaining_quantity": 0,
                    "avg_price": execution["execution_price"],
                    "updated_at": datetime.now(timezone.utc),
                },
            )

            # Create trade record
            session.execute(
                text("""
                INSERT INTO trades (
                    id, challenge_id, order_id, symbol, side, quantity, price,
                    realized_pnl, executed_at, commission
                ) VALUES (
                    :id, :challenge_id, :order_id, :symbol, :side, :quantity, :price,
                    :pnl, :executed_at, :commission
                )
            """),
                {
                    "id": str(uuid.uuid4()),
                    "challenge_id": execution["challenge_id"],
                    "order_id": order_id,
                    "symbol": execution["symbol"],
                    "side": execution["side"],
                    "quantity": execution["quantity"],
                    "price": execution["execution_price"],
                    "pnl": 0.0,  # Will be calculated later
                    "executed_at": datetime.now(timezone.utc),
                    "commission": 0.0,
                },
            )

        session.commit()

        return jsonify(
            {
                "monitored_orders": len(order_engine.active_orders),
                "triggered_orders": len(triggered_orders),
                "executions": triggered_orders,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Order monitoring error: {e}")
        return jsonify({"error": "Failed to monitor orders"}), 500
    finally:
        session.close()


@api_bp.route("/portfolio/<challenge_id>", methods=["GET"])
def get_portfolio(challenge_id):
    """
    Get portfolio summary for a challenge.
    """
    try:
        # Get challenge info
        session = get_db_session()
        challenge = session.execute(
            text("""
            SELECT initial_balance, current_equity FROM challenges
            WHERE id = :challenge_id
        """),
            {"challenge_id": challenge_id},
        ).fetchone()

        if not challenge:
            return jsonify({"error": "Challenge not found"}), 404

        # Get portfolio summary
        portfolio = portfolio_manager.get_portfolio(
            challenge_id, Decimal(str(challenge.initial_balance))
        )

        # Update portfolio from recent trades
        trades = session.execute(
            text("""
            SELECT symbol, side, quantity, price, executed_at
            FROM trades
            WHERE challenge_id = :challenge_id
            ORDER BY executed_at
        """),
            {"challenge_id": challenge_id},
        ).fetchall()

        trade_list = []
        for trade in trades:
            trade_list.append(
                {
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "quantity": float(trade.quantity),
                    "price": float(trade.price),
                    "executed_at": trade.executed_at.isoformat(),
                }
            )

        portfolio_manager.update_portfolio_from_trades(challenge_id, trade_list)

        # Get portfolio summary
        summary = portfolio_manager.get_portfolio_summary(challenge_id)

        return jsonify(summary), 200

    except Exception as e:
        current_app.logger.error(f"Get portfolio error: {e}")
        return jsonify({"error": "Failed to get portfolio"}), 500
    finally:
        session.close()


@api_bp.route("/portfolio/<challenge_id>/analytics", methods=["GET"])
def get_portfolio_analytics(challenge_id):
    """
    Get advanced portfolio analytics.
    """
    try:
        # Get challenge info
        session = get_db_session()
        challenge = session.execute(
            text("""
            SELECT initial_balance FROM challenges
            WHERE id = :challenge_id
        """),
            {"challenge_id": challenge_id},
        ).fetchone()

        if not challenge:
            return jsonify({"error": "Challenge not found"}), 404

        # Get analytics
        analytics = portfolio_manager.get_portfolio_analytics(challenge_id)

        return jsonify(analytics), 200

    except Exception as e:
        current_app.logger.error(f"Get portfolio analytics error: {e}")
        return jsonify({"error": "Failed to get portfolio analytics"}), 500
    finally:
        session.close()


@api_bp.route("/portfolio/<challenge_id>/rebalance", methods=["POST"])
def rebalance_portfolio(challenge_id):
    """
    Generate portfolio rebalancing recommendations.
    """
    try:
        data = request.get_json()

        if not data or "target_allocations" not in data:
            return jsonify({"error": "target_allocations required"}), 400

        target_allocations = {}
        for symbol, percent in data["target_allocations"].items():
            target_allocations[symbol.upper()] = Decimal(str(percent))

        # Get challenge info
        session = get_db_session()
        challenge = session.execute(
            text("""
            SELECT initial_balance FROM challenges
            WHERE id = :challenge_id
        """),
            {"challenge_id": challenge_id},
        ).fetchone()

        if not challenge:
            return jsonify({"error": "Challenge not found"}), 404

        # Get portfolio and generate recommendations
        portfolio = portfolio_manager.get_portfolio(
            challenge_id, Decimal(str(challenge.initial_balance))
        )
        recommendations = portfolio.get_rebalancing_recommendations(target_allocations)

        return jsonify(
            {
                "challenge_id": challenge_id,
                "current_portfolio_value": float(portfolio.total_value),
                "recommendations": recommendations,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Portfolio rebalance error: {e}")
        return jsonify({"error": "Failed to generate rebalancing recommendations"}), 500
    finally:
        session.close()


@api_bp.route("/portfolio/<challenge_id>/positions/<symbol>", methods=["GET"])
def get_position_details(challenge_id, symbol):
    """
    Get detailed information about a specific position.
    """
    try:
        symbol = symbol.upper()

        # Get challenge info
        session = get_db_session()
        challenge = session.execute(
            text("""
            SELECT initial_balance FROM challenges
            WHERE id = :challenge_id
        """),
            {"challenge_id": challenge_id},
        ).fetchone()

        if not challenge:
            return jsonify({"error": "Challenge not found"}), 404

        portfolio = portfolio_manager.get_portfolio(
            challenge_id, Decimal(str(challenge.initial_balance))
        )

        if symbol not in portfolio.positions:
            return jsonify({"error": f"Position {symbol} not found"}), 404

        position = portfolio.positions[symbol]

        # Get trade history for this position
        trades = session.execute(
            text("""
            SELECT side, quantity, price, executed_at, realized_pnl
            FROM trades
            WHERE challenge_id = :challenge_id AND symbol = :symbol
            ORDER BY executed_at DESC
        """),
            {"challenge_id": challenge_id, "symbol": symbol},
        ).fetchall()

        trade_history = []
        for trade in trades:
            trade_history.append(
                {
                    "side": trade.side,
                    "quantity": float(trade.quantity),
                    "price": float(trade.price),
                    "executed_at": trade.executed_at.isoformat(),
                    "realized_pnl": float(trade.realized_pnl or 0),
                }
            )

        return jsonify(
            {
                "symbol": symbol,
                "challenge_id": challenge_id,
                "quantity": float(position.quantity),
                "average_cost": float(position.average_cost),
                "current_price": float(position.current_price),
                "market_value": float(position.market_value),
                "unrealized_pnl": float(position.unrealized_pnl),
                "unrealized_pnl_percent": float(position.unrealized_pnl_percent),
                "entry_date": position.entry_date.isoformat(),
                "last_updated": position.last_updated.isoformat(),
                "trade_history": trade_history,
                "trade_count": len(trade_history),
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Get position details error: {e}")
        return jsonify({"error": "Failed to get position details"}), 500
    finally:
        session.close()


@api_bp.route("/portfolio/<challenge_id>/performance", methods=["GET"])
def get_portfolio_performance(challenge_id):
    """
    Get detailed portfolio performance metrics.
    """
    try:
        # Get challenge info
        session = get_db_session()
        challenge = session.execute(
            text("""
            SELECT initial_balance, created_at FROM challenges
            WHERE id = :challenge_id
        """),
            {"challenge_id": challenge_id},
        ).fetchone()

        if not challenge:
            return jsonify({"error": "Challenge not found"}), 404

        portfolio = portfolio_manager.get_portfolio(
            challenge_id, Decimal(str(challenge.initial_balance))
        )

        # Calculate performance metrics over time
        # This is a simplified version - in production, you'd store historical snapshots
        current_time = datetime.now(timezone.utc)
        challenge_age_days = (current_time - challenge.created_at).days

        performance = {
            "challenge_id": challenge_id,
            "challenge_age_days": challenge_age_days,
            "initial_balance": float(challenge.initial_balance),
            "current_value": float(portfolio.total_value),
            "total_return": float(portfolio.return_percentage),
            "daily_return": float(
                portfolio.return_percentage / max(challenge_age_days, 1)
            ),
            "monthly_return": float(
                portfolio.return_percentage / max(challenge_age_days / 30, 1)
            ),
            "annualized_return": float(
                portfolio.return_percentage * (365 / max(challenge_age_days, 1))
            ),
            "win_rate": 0.0,  # Would be calculated from trade history
            "profit_factor": 0.0,  # Would be calculated from trade P&L
            "max_drawdown": float(portfolio.risk_metrics["max_drawdown"]),
            "volatility": float(portfolio.risk_metrics["volatility"]),
            "sharpe_ratio": float(portfolio.risk_metrics["sharpe_ratio"]),
            "calmar_ratio": float(
                portfolio.return_percentage
                / max(portfolio.risk_metrics["max_drawdown"], 0.01)
            ),
            "sortino_ratio": float(
                portfolio.risk_metrics["sharpe_ratio"] * 0.8
            ),  # Simplified
            "alpha": 0.0,  # Would compare to benchmark
            "beta": float(portfolio.risk_metrics["beta"]),
        }

        return jsonify(performance), 200

    except Exception as e:
        current_app.logger.error(f"Get portfolio performance error: {e}")
        return jsonify({"error": "Failed to get portfolio performance"}), 500
    finally:
        session.close()


@api_bp.route("/market/symbols/<symbol>", methods=["GET"])
def get_symbol_details(symbol):
    """
    Get detailed information for a specific symbol.

    Includes price history, company info, and trading metrics.
    """
    try:
        symbol = symbol.upper()

        # Get current price
        current_price, previous_close = market_data.get_stock_price(symbol)

        if current_price is None:
            return jsonify(
                {"error": "Symbol not found or data unavailable", "symbol": symbol}
            ), 404

        # Calculate metrics
        change = float(current_price - previous_close) if previous_close else 0
        change_percent = (
            float((change / float(previous_close)) * 100)
            if previous_close and previous_close != 0
            else 0
        )

        # Market information
        is_casablanca = symbol.endswith(".MA")
        market = "Casablanca Stock Exchange" if is_casablanca else "Global Markets"
        currency = "MAD" if is_casablanca else "USD"

        return jsonify(
            {
                "symbol": symbol,
                "market": market,
                "currency": currency,
                "current_price": float(current_price),
                "previous_close": float(previous_close) if previous_close else None,
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "status": "active",
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "data_source": "casablanca" if is_casablanca else "yahoo",
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Symbol details error for {symbol}: {e}")
        return jsonify({"error": "Failed to get symbol details"}), 500
