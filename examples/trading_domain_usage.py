"""
Trading Domain Usage Examples

This file demonstrates how to use the Trading domain for trade execution,
position management, and P&L calculation.
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from src.domains.trading.domain.entities import Order
from src.domains.trading.domain.trade import Position, Trade, TradingAccount
from src.domains.trading.domain.value_objects import (
    Commission,
    Fill,
    OrderSide,
    OrderType,
    PositionSide,
    Price,
    Quantity,
    Symbol,
    TimeInForce,
    TradeId,
    TradeType,
)
from src.domains.trading.application.trade_execution_service import (
    PnLCalculationService,
    PositionManagementService,
    TradeExecutionService,
    TradingMetricsService,
)
from src.shared.events.event_bus import InMemoryEventBus
from src.shared.utils.money import Money


async def example_1_execute_single_trade():
    """Example 1: Execute a single trade and create position."""
    
    print("=== Example 1: Execute Single Trade ===")
    
    # Setup
    user_id = uuid4()
    event_bus = InMemoryEventBus()
    execution_service = TradeExecutionService(event_bus)
    
    # Create order (normally comes from order management)
    order = Order(
        user_id=user_id,
        symbol=Symbol("EURUSD"),
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Quantity(Decimal("10000")),
        time_in_force=TimeInForce.GTC,
    )
    
    # Create fill (normally comes from execution venue)
    fill = Fill(
        quantity=Quantity(Decimal("10000")),
        price=Price(Money(Decimal("1.0850"), "USD")),
        fill_id="FILL_001",
        timestamp=datetime.utcnow().isoformat(),
        commission=Money(Decimal("5.00"), "USD"),
    )
    
    # Execute trade
    trade = await execution_service.execute_trade(
        order=order,
        fill=fill,
        trade_id="TRADE_001",
        commission_amount=Money(Decimal("5.00"), "USD"),
    )
    
    print(f"Trade executed: {trade.trade_id}")
    print(f"Symbol: {trade.symbol}")
    print(f"Side: {trade.side.value}")
    print(f"Quantity: {trade.quantity.value}")
    print(f"Price: {trade.price.value}")
    print(f"Gross Value: {trade.gross_value}")
    print(f"Net Value: {trade.net_value}")
    print(f"Commission: {trade.commission.amount}")
    
    # Open position from trade
    position = await execution_service.open_position(trade)
    
    print(f"\nPosition opened: {position.id}")
    print(f"Side: {position.side.value}")
    print(f"Entry Price: {position.entry_price.value}")
    print(f"Entry Value: {position.entry_value}")
    
    return trade, position


async def example_2_position_lifecycle():
    """Example 2: Complete position lifecycle with multiple trades."""
    
    print("\n=== Example 2: Position Lifecycle ===")
    
    # Setup
    user_id = uuid4()
    event_bus = InMemoryEventBus()
    execution_service = TradeExecutionService(event_bus)
    
    # Initial position opening trade
    opening_trade = Trade(
        trade_id=TradeId("TRADE_OPEN"),
        user_id=user_id,
        symbol=Symbol("GBPUSD"),
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("5000")),
        price=Price(Money(Decimal("1.2500"), "USD")),
        order_id=uuid4(),
        fill=Fill(
            quantity=Quantity(Decimal("5000")),
            price=Price(Money(Decimal("1.2500"), "USD")),
            fill_id="FILL_OPEN",
        ),
        trade_type=TradeType.OPEN,
        commission=Commission(Money(Decimal("2.50"), "USD")),
    )
    
    # Create position
    position = Position(
        user_id=user_id,
        symbol=Symbol("GBPUSD"),
        side=PositionSide.LONG,
        opening_trade=opening_trade,
    )
    
    print(f"Position opened: {position.quantity.value} {position.symbol} @ {position.entry_price.value}")
    
    # Add to position (increase size)
    increase_trade = Trade(
        trade_id=TradeId("TRADE_INCREASE"),
        user_id=user_id,
        symbol=Symbol("GBPUSD"),
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("3000")),
        price=Price(Money(Decimal("1.2600"), "USD")),
        order_id=uuid4(),
        fill=Fill(
            quantity=Quantity(Decimal("3000")),
            price=Price(Money(Decimal("1.2600"), "USD")),
            fill_id="FILL_INCREASE",
        ),
        trade_type=TradeType.INCREASE,
        commission=Commission(Money(Decimal("1.50"), "USD")),
    )
    
    # Update position
    position.update_quantity(increase_trade)
    
    print(f"Position increased: {position.quantity.value} @ {position.entry_price.value} (weighted avg)")
    
    # Update market price and calculate P&L
    current_price = Price(Money(Decimal("1.2750"), "USD"))
    unrealized_pnl = position.update_market_price(current_price)
    
    print(f"Current price: {current_price.value}")
    print(f"Unrealized P&L: {position.unrealized_pnl}")
    print(f"P&L %: {(position.unrealized_pnl.amount / position.entry_value.amount * 100):.2f}%")
    
    # Partial close
    partial_close_trade = Trade(
        trade_id=TradeId("TRADE_PARTIAL_CLOSE"),
        user_id=user_id,
        symbol=Symbol("GBPUSD"),
        side=OrderSide.SELL,
        quantity=Quantity(Decimal("3000")),
        price=Price(Money(Decimal("1.2800"), "USD")),
        order_id=uuid4(),
        fill=Fill(
            quantity=Quantity(Decimal("3000")),
            price=Price(Money(Decimal("1.2800"), "USD")),
            fill_id="FILL_PARTIAL",
        ),
        trade_type=TradeType.REDUCE,
        commission=Commission(Money(Decimal("1.50"), "USD")),
    )
    
    # Reduce position
    position.update_quantity(partial_close_trade)
    
    print(f"Position reduced: {position.quantity.value} remaining")
    print(f"Realized P&L: {position.realized_pnl}")
    
    # Final close
    closing_trade = Trade(
        trade_id=TradeId("TRADE_CLOSE"),
        user_id=user_id,
        symbol=Symbol("GBPUSD"),
        side=OrderSide.SELL,
        quantity=Quantity(Decimal("5000")),
        price=Price(Money(Decimal("1.2850"), "USD")),
        order_id=uuid4(),
        fill=Fill(
            quantity=Quantity(Decimal("5000")),
            price=Price(Money(Decimal("1.2850"), "USD")),
            fill_id="FILL_CLOSE",
        ),
        trade_type=TradeType.CLOSE,
        commission=Commission(Money(Decimal("2.50"), "USD")),
    )
    
    # Close position
    final_pnl = position.close_position(closing_trade)
    
    print(f"Position closed")
    print(f"Final realized P&L: {position.realized_pnl}")
    print(f"Total commission: {position.total_commission}")
    print(f"Position duration: {(position.closed_at - position.opened_at).total_seconds()} seconds")
    
    return position


async def example_3_trading_account_management():
    """Example 3: Trading account with multiple positions."""
    
    print("\n=== Example 3: Trading Account Management ===")
    
    # Setup
    user_id = uuid4()
    initial_balance = Money(Decimal("100000"), "USD")
    
    # Create trading account
    account = TradingAccount(
        user_id=user_id,
        account_currency="USD",
        initial_balance=initial_balance,
    )
    
    print(f"Trading account created")
    print(f"Initial balance: {account.initial_balance}")
    print(f"Current balance: {account.current_balance}")
    
    # Simulate multiple trades and positions
    trades_data = [
        {"symbol": "EURUSD", "side": "BUY", "quantity": 10000, "price": 1.0850, "pnl": 150},
        {"symbol": "GBPUSD", "side": "BUY", "quantity": 8000, "price": 1.2500, "pnl": -75},
        {"symbol": "USDJPY", "side": "SELL", "quantity": 12000, "price": 110.50, "pnl": 200},
        {"symbol": "AUDUSD", "side": "BUY", "quantity": 15000, "price": 0.7250, "pnl": -50},
        {"symbol": "USDCAD", "side": "SELL", "quantity": 9000, "price": 1.3500, "pnl": 125},
    ]
    
    positions = []
    
    for i, trade_data in enumerate(trades_data):
        # Create mock trade
        trade = Trade(
            trade_id=TradeId(f"TRADE_{i+1}"),
            user_id=user_id,
            symbol=Symbol(trade_data["symbol"]),
            side=OrderSide(trade_data["side"]),
            quantity=Quantity(Decimal(str(trade_data["quantity"]))),
            price=Price(Money(Decimal(str(trade_data["price"])), "USD")),
            order_id=uuid4(),
            fill=Fill(
                quantity=Quantity(Decimal(str(trade_data["quantity"]))),
                price=Price(Money(Decimal(str(trade_data["price"])), "USD")),
                fill_id=f"FILL_{i+1}",
            ),
            commission=Commission(Money(Decimal("5.00"), "USD")),
        )
        
        # Record trade in account
        account.record_trade(trade)
        
        # Create position
        position_side = PositionSide.LONG if trade_data["side"] == "BUY" else PositionSide.SHORT
        position = Position(
            user_id=user_id,
            symbol=Symbol(trade_data["symbol"]),
            side=position_side,
            opening_trade=trade,
        )
        
        # Record position opening
        account.record_position_opened(position)
        
        # Simulate position close with P&L
        pnl_amount = Money(Decimal(str(trade_data["pnl"])), "USD")
        position._realized_pnl = pnl_amount
        position._is_open = False
        position._closed_at = datetime.utcnow()
        
        # Record position closing
        from ..domain.value_objects import PnL, PnLType
        realized_pnl = PnL(pnl_amount, PnLType.REALIZED, "USD")
        account.record_position_closed(position, realized_pnl)
        
        positions.append(position)
    
    print(f"\nAccount after {len(trades_data)} trades:")
    print(f"Total trades: {account.total_trades}")
    print(f"Winning trades: {account.winning_trades}")
    print(f"Losing trades: {account.losing_trades}")
    print(f"Win rate: {account.win_rate:.1f}%")
    print(f"Total realized P&L: {account.total_realized_pnl}")
    print(f"Current balance: {account.current_balance}")
    print(f"Largest win: {account.largest_win}")
    print(f"Largest loss: {account.largest_loss}")
    print(f"Total commission: {account.total_commission}")
    
    return account, positions


async def example_4_pnl_calculations():
    """Example 4: P&L calculations and price updates."""
    
    print("\n=== Example 4: P&L Calculations ===")
    
    # Setup
    user_id = uuid4()
    event_bus = InMemoryEventBus()
    pnl_service = PnLCalculationService(event_bus)
    
    # Create position
    opening_trade = Trade(
        trade_id=TradeId("TRADE_PNL"),
        user_id=user_id,
        symbol=Symbol("EURUSD"),
        side=OrderSide.BUY,
        quantity=Quantity(Decimal("50000")),
        price=Price(Money(Decimal("1.0800"), "USD")),
        order_id=uuid4(),
        fill=Fill(
            quantity=Quantity(Decimal("50000")),
            price=Price(Money(Decimal("1.0800"), "USD")),
            fill_id="FILL_PNL",
        ),
        commission=Commission(Money(Decimal("10.00"), "USD")),
    )
    
    position = Position(
        user_id=user_id,
        symbol=Symbol("EURUSD"),
        side=PositionSide.LONG,
        opening_trade=opening_trade,
    )
    
    print(f"Position: {position.quantity.value} {position.symbol} @ {position.entry_price.value}")
    print(f"Entry value: {position.entry_value}")
    
    # Test different price scenarios
    price_scenarios = [
        {"price": 1.0850, "description": "50 pips profit"},
        {"price": 1.0750, "description": "50 pips loss"},
        {"price": 1.0900, "description": "100 pips profit"},
        {"price": 1.0700, "description": "100 pips loss"},
        {"price": 1.0800, "description": "Break-even"},
    ]
    
    for scenario in price_scenarios:
        current_price = Price(Money(Decimal(str(scenario["price"])), "USD"))
        total_pnl = await pnl_service.calculate_position_pnl(position, current_price)
        
        pnl_percentage = (
            position.unrealized_pnl.amount / position.entry_value.amount * 100
            if position.entry_value.amount != 0 else 0
        )
        
        print(f"\n{scenario['description']}:")
        print(f"  Price: {current_price.value}")
        print(f"  Unrealized P&L: {position.unrealized_pnl}")
        print(f"  P&L %: {pnl_percentage:.2f}%")
        print(f"  Total P&L: {total_pnl}")
    
    return position


async def example_5_trading_metrics():
    """Example 5: Calculate trading metrics and statistics."""
    
    print("\n=== Example 5: Trading Metrics ===")
    
    # Setup
    metrics_service = TradingMetricsService()
    
    # Sample trading data
    winning_trades = 15
    total_trades = 25
    total_wins = Money(Decimal("2500"), "USD")
    total_losses = Money(Decimal("1200"), "USD")
    
    # Sample returns for Sharpe ratio
    daily_returns = [
        Decimal("0.02"), Decimal("-0.01"), Decimal("0.03"), Decimal("0.01"),
        Decimal("-0.02"), Decimal("0.04"), Decimal("0.00"), Decimal("0.02"),
        Decimal("-0.01"), Decimal("0.03"), Decimal("0.01"), Decimal("-0.02"),
    ]
    
    # Sample equity curve for max drawdown
    equity_curve = [
        Money(Decimal("100000"), "USD"), Money(Decimal("101000"), "USD"),
        Money(Decimal("99500"), "USD"), Money(Decimal("102000"), "USD"),
        Money(Decimal("101500"), "USD"), Money(Decimal("98000"), "USD"),
        Money(Decimal("103000"), "USD"), Money(Decimal("104500"), "USD"),
        Money(Decimal("102000"), "USD"), Money(Decimal("105000"), "USD"),
    ]
    
    # Calculate metrics
    win_rate = metrics_service.calculate_win_rate(winning_trades, total_trades)
    profit_factor = metrics_service.calculate_profit_factor(total_wins, total_losses)
    sharpe_ratio = metrics_service.calculate_sharpe_ratio(daily_returns)
    max_drawdown = metrics_service.calculate_max_drawdown(equity_curve)
    
    print(f"Trading Metrics:")
    print(f"  Total trades: {total_trades}")
    print(f"  Winning trades: {winning_trades}")
    print(f"  Win rate: {win_rate:.1f}%")
    print(f"  Profit factor: {profit_factor:.2f}")
    print(f"  Sharpe ratio: {sharpe_ratio:.2f}")
    print(f"  Max drawdown: {max_drawdown}")
    print(f"  Total wins: {total_wins}")
    print(f"  Total losses: {total_losses}")
    print(f"  Net P&L: {total_wins - Money(total_losses.amount, 'USD')}")
    
    return {
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
    }


async def example_6_event_driven_integration():
    """Example 6: Event-driven integration with other domains."""
    
    print("\n=== Example 6: Event-Driven Integration ===")
    
    # Setup event bus with handlers
    event_bus = InMemoryEventBus()
    
    # Mock event handlers (would be in other domains)
    trade_events = []
    position_events = []
    pnl_events = []
    
    async def handle_trade_executed(event):
        trade_events.append(event)
        print(f"📊 Challenge Engine: Trade executed - {event.symbol} {event.side} {event.quantity}")
    
    async def handle_position_opened(event):
        position_events.append(event)
        print(f"📈 Rules Engine: Position opened - {event.symbol} {event.side}")
    
    async def handle_position_closed(event):
        position_events.append(event)
        print(f"📉 Rules Engine: Position closed - P&L: {event.realized_pnl}")
    
    async def handle_pnl_calculated(event):
        pnl_events.append(event)
        print(f"💰 Risk Engine: P&L updated - Total: {event.total_pnl}")
    
    async def handle_daily_pnl(event):
        pnl_events.append(event)
        print(f"📅 Challenge Engine: Daily P&L - {event.daily_pnl} on {event.date}")
    
    # Register event handlers
    event_bus.subscribe("TradeExecuted", handle_trade_executed)
    event_bus.subscribe("PositionOpened", handle_position_opened)
    event_bus.subscribe("PositionClosed", handle_position_closed)
    event_bus.subscribe("PnLCalculated", handle_pnl_calculated)
    event_bus.subscribe("DailyPnLCalculated", handle_daily_pnl)
    
    # Execute trading operations
    user_id = uuid4()
    execution_service = TradeExecutionService(event_bus)
    
    # Create and execute trade
    order = Order(
        user_id=user_id,
        symbol=Symbol("EURUSD"),
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Quantity(Decimal("10000")),
    )
    
    fill = Fill(
        quantity=Quantity(Decimal("10000")),
        price=Price(Money(Decimal("1.0850"), "USD")),
        fill_id="FILL_EVENT",
        commission=Money(Decimal("5.00"), "USD"),
    )
    
    # Execute trade (will emit TradeExecuted event)
    trade = await execution_service.execute_trade(order, fill, "TRADE_EVENT")
    
    # Open position (will emit PositionOpened event)
    position = await execution_service.open_position(trade)
    
    # Update price (will emit PnLCalculated event)
    new_price = Price(Money(Decimal("1.0900"), "USD"))
    await execution_service.update_position_price(position, new_price)
    
    # Close position (will emit PositionClosed event)
    closing_trade = Trade(
        trade_id=TradeId("TRADE_CLOSE_EVENT"),
        user_id=user_id,
        symbol=Symbol("EURUSD"),
        side=OrderSide.SELL,
        quantity=Quantity(Decimal("10000")),
        price=Price(Money(Decimal("1.0900"), "USD")),
        order_id=uuid4(),
        fill=Fill(
            quantity=Quantity(Decimal("10000")),
            price=Price(Money(Decimal("1.0900"), "USD")),
            fill_id="FILL_CLOSE_EVENT",
        ),
        trade_type=TradeType.CLOSE,
    )
    
    await execution_service.close_position(position, closing_trade)
    
    # Create trading account and calculate daily P&L
    account = TradingAccount(user_id=user_id)
    daily_pnl = account.calculate_daily_pnl(datetime.utcnow())
    
    # Publish account events
    for event in account.domain_events:
        await event_bus.publish(event)
    
    print(f"\nEvent Summary:")
    print(f"  Trade events: {len(trade_events)}")
    print(f"  Position events: {len(position_events)}")
    print(f"  P&L events: {len(pnl_events)}")
    
    return {
        "trade_events": trade_events,
        "position_events": position_events,
        "pnl_events": pnl_events,
    }


async def main():
    """Run all trading domain examples."""
    
    print("🚀 Trading Domain Usage Examples")
    print("=" * 50)
    
    try:
        # Run examples
        await example_1_execute_single_trade()
        await example_2_position_lifecycle()
        await example_3_trading_account_management()
        await example_4_pnl_calculations()
        await example_5_trading_metrics()
        await example_6_event_driven_integration()
        
        print("\n✅ All trading domain examples completed successfully!")
        
        print("\n📋 Key Takeaways:")
        print("• Trading domain focuses purely on execution recording and P&L calculation")
        print("• No business logic about challenges or risk management")
        print("• All state changes emit events for other domains to consume")
        print("• Financial accuracy with Decimal precision for all calculations")
        print("• Complete audit trail of all trades and position changes")
        print("• Event-driven integration enables loose coupling between domains")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())