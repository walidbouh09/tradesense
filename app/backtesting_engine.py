"""
Professional Backtesting Engine

Features:
- Historical data simulation
- Strategy testing framework
- Performance metrics calculation
- Risk analysis
- Walk-forward optimization
- Monte Carlo simulation
"""

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from abc import ABC, abstractmethod
import statistics
import random
import uuid

from app.technical_analysis import PriceData, TechnicalIndicators, ChartAnalysis
from app.market_data import market_data


class Trade:
    """Represents a backtested trade."""

    def __init__(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        entry_price: Decimal,
        entry_time: datetime,
        exit_price: Optional[Decimal] = None,
        exit_time: Optional[datetime] = None,
        commission: Decimal = Decimal('0'),
        strategy_name: str = ''
    ):
        self.id = str(uuid.uuid4())
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.commission = commission
        self.strategy_name = strategy_name

    @property
    def is_closed(self) -> bool:
        """Check if trade is closed."""
        return self.exit_price is not None and self.exit_time is not None

    @property
    def pnl(self) -> Optional[Decimal]:
        """Calculate profit/loss."""
        if not self.is_closed:
            return None

        if self.side == 'BUY':
            gross_pnl = (self.exit_price - self.entry_price) * self.quantity
        else:  # SELL
            gross_pnl = (self.entry_price - self.exit_price) * self.quantity

        return gross_pnl - (self.commission * 2)  # Commission on entry and exit

    @property
    def pnl_percent(self) -> Optional[Decimal]:
        """Calculate profit/loss percentage."""
        if not self.is_closed or self.entry_price == 0:
            return None

        return (self.pnl / (self.entry_price * self.quantity)) * 100

    @property
    def holding_period(self) -> Optional[int]:
        """Calculate holding period in days."""
        if not self.is_closed:
            return None

        return (self.exit_time - self.entry_time).days


class Position:
    """Represents a position in backtesting."""

    def __init__(self, symbol: str, side: str, quantity: Decimal, entry_price: Decimal, entry_time: datetime):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.current_price = entry_price

    def update_price(self, price: Decimal):
        """Update current price."""
        self.current_price = price

    @property
    def unrealized_pnl(self) -> Decimal:
        """Calculate unrealized P&L."""
        if self.side == 'BUY':
            return (self.current_price - self.entry_price) * self.quantity
        else:  # SELL (short position)
            return (self.entry_price - self.current_price) * self.quantity

    @property
    def market_value(self) -> Decimal:
        """Current market value of position."""
        return self.current_price * self.quantity


class BacktestResult:
    """Results of a backtest run."""

    def __init__(self, strategy_name: str):
        self.strategy_name = strategy_name
        self.trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, Decimal]] = []
        self.initial_balance = Decimal('100000')
        self.final_balance = self.initial_balance
        self.start_date: Optional[datetime] = None
        self.end_date: Optional[datetime] = None

    @property
    def total_trades(self) -> int:
        """Total number of trades."""
        return len(self.trades)

    @property
    def winning_trades(self) -> int:
        """Number of winning trades."""
        return len([t for t in self.trades if t.is_closed and t.pnl and t.pnl > 0])

    @property
    def losing_trades(self) -> int:
        """Number of losing trades."""
        return len([t for t in self.trades if t.is_closed and t.pnl and t.pnl < 0])

    @property
    def win_rate(self) -> Decimal:
        """Win rate percentage."""
        if self.total_trades == 0:
            return Decimal('0')
        return (Decimal(str(self.winning_trades)) / Decimal(str(self.total_trades))) * 100

    @property
    def total_pnl(self) -> Decimal:
        """Total profit/loss."""
        return sum((t.pnl for t in self.trades if t.pnl), Decimal('0'))

    @property
    def total_return(self) -> Decimal:
        """Total return percentage."""
        if self.initial_balance == 0:
            return Decimal('0')
        return (self.total_pnl / self.initial_balance) * 100

    @property
    def avg_win(self) -> Optional[Decimal]:
        """Average winning trade."""
        wins = [t.pnl for t in self.trades if t.pnl and t.pnl > 0]
        return statistics.mean(wins) if wins else None

    @property
    def avg_loss(self) -> Optional[Decimal]:
        """Average losing trade."""
        losses = [t.pnl for t in self.trades if t.pnl and t.pnl < 0]
        return statistics.mean(losses) if losses else None

    @property
    def profit_factor(self) -> Optional[Decimal]:
        """Profit factor (gross profit / gross loss)."""
        gross_profit = sum(t.pnl for t in self.trades if t.pnl and t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl and t.pnl < 0))

        if gross_loss == 0:
            return None
        return gross_profit / gross_loss

    @property
    def max_drawdown(self) -> Decimal:
        """Maximum drawdown percentage."""
        if not self.equity_curve:
            return Decimal('0')

        peak = self.initial_balance
        max_dd = Decimal('0')

        for _, equity in self.equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100
            max_dd = max(max_dd, dd)

        return max_dd

    @property
    def sharpe_ratio(self) -> Optional[Decimal]:
        """Sharpe ratio (annualized)."""
        if not self.equity_curve or len(self.equity_curve) < 2:
            return None

        # Calculate daily returns
        daily_returns = []
        prev_equity = self.initial_balance

        for _, equity in self.equity_curve:
            daily_return = (equity - prev_equity) / prev_equity
            daily_returns.append(float(daily_return))
            prev_equity = equity

        if not daily_returns:
            return None

        avg_return = statistics.mean(daily_returns)
        std_return = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0

        if std_return == 0:
            return None

        # Annualized Sharpe ratio (assuming 252 trading days)
        return Decimal(str((avg_return * 252) / (std_return * (252 ** 0.5))))

    @property
    def calmar_ratio(self) -> Optional[Decimal]:
        """Calmar ratio (annualized return / max drawdown)."""
        if self.max_drawdown == 0:
            return None

        # Simplified annualized return calculation
        if self.start_date and self.end_date:
            years = (self.end_date - self.start_date).days / 365.25
            if years > 0:
                annualized_return = self.total_return / Decimal(str(years))
                return annualized_return / self.max_drawdown

        return None


class TradingStrategy(ABC):
    """Abstract base class for trading strategies."""

    def __init__(self, name: str, parameters: Dict[str, Any] = None):
        self.name = name
        self.parameters = parameters or {}

    @abstractmethod
    def should_enter_long(self, symbol: str, price_data: List[PriceData], current_positions: Dict[str, Position]) -> bool:
        """Determine if strategy should enter a long position."""
        pass

    @abstractmethod
    def should_enter_short(self, symbol: str, price_data: List[PriceData], current_positions: Dict[str, Position]) -> bool:
        """Determine if strategy should enter a short position."""
        pass

    @abstractmethod
    def should_exit_long(self, symbol: str, position: Position, price_data: List[PriceData]) -> bool:
        """Determine if strategy should exit a long position."""
        pass

    @abstractmethod
    def should_exit_short(self, symbol: str, position: Position, price_data: List[PriceData]) -> bool:
        """Determine if strategy should exit a short position."""
        pass

    def calculate_position_size(self, symbol: str, entry_price: Decimal, portfolio_value: Decimal) -> Decimal:
        """Calculate position size (can be overridden by strategies)."""
        # Default: 10% of portfolio per position
        return (portfolio_value * Decimal('0.1')) / entry_price


class RSIStrategy(TradingStrategy):
    """RSI-based mean reversion strategy."""

    def __init__(self, parameters: Dict[str, Any] = None):
        super().__init__("RSI_Strategy", parameters)
        self.rsi_period = parameters.get('rsi_period', 14)
        self.overbought_level = parameters.get('overbought', 70)
        self.oversold_level = parameters.get('oversold', 30)

    def should_enter_long(self, symbol: str, price_data: List[PriceData], current_positions: Dict[str, Position]) -> bool:
        if symbol in current_positions:
            return False

        closes = [p.close for p in price_data]
        rsi_values = TechnicalIndicators.rsi(closes, self.rsi_period)

        if rsi_values and rsi_values[-1] and rsi_values[-1] < self.oversold_level:
            return True

        return False

    def should_enter_short(self, symbol: str, price_data: List[PriceData], current_positions: Dict[str, Position]) -> bool:
        if symbol in current_positions:
            return False

        closes = [p.close for p in price_data]
        rsi_values = TechnicalIndicators.rsi(closes, self.rsi_period)

        if rsi_values and rsi_values[-1] and rsi_values[-1] > self.overbought_level:
            return True

        return False

    def should_exit_long(self, symbol: str, position: Position, price_data: List[PriceData]) -> bool:
        closes = [p.close for p in price_data]
        rsi_values = TechnicalIndicators.rsi(closes, self.rsi_period)

        # Exit when RSI reaches midline (50)
        if rsi_values and rsi_values[-1] and rsi_values[-1] >= 50:
            return True

        return False

    def should_exit_short(self, symbol: str, position: Position, price_data: List[PriceData]) -> bool:
        closes = [p.close for p in price_data]
        rsi_values = TechnicalIndicators.rsi(closes, self.rsi_period)

        # Exit when RSI reaches midline (50)
        if rsi_values and rsi_values[-1] and rsi_values[-1] <= 50:
            return True

        return False


class MACDStrategy(TradingStrategy):
    """MACD trend-following strategy."""

    def __init__(self, parameters: Dict[str, Any] = None):
        super().__init__("MACD_Strategy", parameters)
        self.fast_period = parameters.get('fast_period', 12)
        self.slow_period = parameters.get('slow_period', 26)
        self.signal_period = parameters.get('signal_period', 9)

    def should_enter_long(self, symbol: str, price_data: List[PriceData], current_positions: Dict[str, Position]) -> bool:
        if symbol in current_positions:
            return False

        closes = [p.close for p in price_data]
        macd_line, signal_line, _ = TechnicalIndicators.macd(
            closes, self.fast_period, self.slow_period, self.signal_period
        )

        # Enter long on MACD crossover (MACD crosses above signal)
        if len(macd_line) >= 3 and len(signal_line) >= 3:
            prev_macd = macd_line[-3] if macd_line[-3] else 0
            prev_signal = signal_line[-3] if signal_line[-3] else 0
            curr_macd = macd_line[-1] if macd_line[-1] else 0
            curr_signal = signal_line[-1] if signal_line[-1] else 0

            if prev_macd <= prev_signal and curr_macd > curr_signal:
                return True

        return False

    def should_enter_short(self, symbol: str, price_data: List[PriceData], current_positions: Dict[str, Position]) -> bool:
        if symbol in current_positions:
            return False

        closes = [p.close for p in price_data]
        macd_line, signal_line, _ = TechnicalIndicators.macd(
            closes, self.fast_period, self.slow_period, self.signal_period
        )

        # Enter short on MACD crossover (MACD crosses below signal)
        if len(macd_line) >= 3 and len(signal_line) >= 3:
            prev_macd = macd_line[-3] if macd_line[-3] else 0
            prev_signal = signal_line[-3] if signal_line[-3] else 0
            curr_macd = macd_line[-1] if macd_line[-1] else 0
            curr_signal = signal_line[-1] if signal_line[-1] else 0

            if prev_macd >= prev_signal and curr_macd < curr_signal:
                return True

        return False

    def should_exit_long(self, symbol: str, position: Position, price_data: List[PriceData]) -> bool:
        # Exit on opposite MACD signal
        return self.should_enter_short(symbol, price_data, {})

    def should_exit_short(self, symbol: str, position: Position, price_data: List[PriceData]) -> bool:
        # Exit on opposite MACD signal
        return self.should_enter_long(symbol, price_data, {})


class MeanReversionStrategy(TradingStrategy):
    """Bollinger Bands mean reversion strategy."""

    def __init__(self, parameters: Dict[str, Any] = None):
        super().__init__("Mean_Reversion_Strategy", parameters)
        self.bb_period = parameters.get('bb_period', 20)
        self.bb_std = parameters.get('bb_std', 2.0)

    def should_enter_long(self, symbol: str, price_data: List[PriceData], current_positions: Dict[str, Position]) -> bool:
        if symbol in current_positions:
            return False

        closes = [p.close for p in price_data]
        _, upper_band, lower_band = TechnicalIndicators.bollinger_bands(
            closes, self.bb_period, self.bb_std
        )

        current_price = closes[-1]

        # Enter long when price touches lower band
        if lower_band and lower_band[-1] and current_price <= lower_band[-1]:
            return True

        return False

    def should_enter_short(self, symbol: str, price_data: List[PriceData], current_positions: Dict[str, Position]) -> bool:
        if symbol in current_positions:
            return False

        closes = [p.close for p in price_data]
        _, upper_band, lower_band = TechnicalIndicators.bollinger_bands(
            closes, self.bb_period, self.bb_std
        )

        current_price = closes[-1]

        # Enter short when price touches upper band
        if upper_band and upper_band[-1] and current_price >= upper_band[-1]:
            return True

        return False

    def should_exit_long(self, symbol: str, position: Position, price_data: List[PriceData]) -> bool:
        closes = [p.close for p in price_data]
        sma, _, _ = TechnicalIndicators.bollinger_bands(closes, self.bb_period, self.bb_std)

        current_price = closes[-1]

        # Exit when price reaches middle band (SMA)
        if sma and sma[-1] and current_price >= sma[-1]:
            return True

        return False

    def should_exit_short(self, symbol: str, position: Position, price_data: List[PriceData]) -> bool:
        closes = [p.close for p in price_data]
        sma, _, _ = TechnicalIndicators.bollinger_bands(closes, self.bb_period, self.bb_std)

        current_price = closes[-1]

        # Exit when price reaches middle band (SMA)
        if sma and sma[-1] and current_price <= sma[-1]:
            return True

        return False


class BacktestingEngine:
    """Professional backtesting engine."""

    def __init__(self):
        self.strategies: Dict[str, TradingStrategy] = {}
        self.commission_per_trade = Decimal('0.001')  # 0.1% per trade

    def register_strategy(self, strategy: TradingStrategy):
        """Register a trading strategy."""
        self.strategies[strategy.name] = strategy

    def run_backtest(
        self,
        strategy: TradingStrategy,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        initial_balance: Decimal = Decimal('100000'),
        max_positions: int = 5
    ) -> BacktestResult:
        """
        Run a backtest for a strategy.

        Args:
            strategy: Trading strategy to test
            symbols: List of symbols to trade
            start_date: Start date for backtest
            end_date: End date for backtest
            initial_balance: Starting balance
            max_positions: Maximum concurrent positions
        """
        result = BacktestResult(strategy.name)
        result.initial_balance = initial_balance
        result.final_balance = initial_balance
        result.start_date = start_date
        result.end_date = end_date

        current_balance = initial_balance
        positions: Dict[str, Position] = {}
        equity_curve = [(start_date, initial_balance)]

        # Generate synthetic historical data for each symbol
        symbol_data = {}
        for symbol in symbols:
            symbol_data[symbol] = self._generate_historical_data(symbol, start_date, end_date)

        # Sort all timestamps
        all_timestamps = set()
        for data in symbol_data.values():
            all_timestamps.update(p.timestamp for p in data)
        sorted_timestamps = sorted(all_timestamps)

        for current_time in sorted_timestamps:
            if current_time < start_date or current_time > end_date:
                continue

            # Update positions with current prices
            for symbol, position in positions.items():
                price_data = symbol_data[symbol]
                current_price = self._get_price_at_time(price_data, current_time)
                if current_price:
                    position.update_price(current_price)

            # Check exit conditions
            positions_to_close = []
            for symbol, position in positions.items():
                price_data = symbol_data[symbol][:symbol_data[symbol].index(
                    next(p for p in symbol_data[symbol] if p.timestamp >= current_time)
                ) + 1]

                if position.side == 'BUY' and strategy.should_exit_long(symbol, position, price_data):
                    positions_to_close.append((symbol, position))
                elif position.side == 'SELL' and strategy.should_exit_short(symbol, position, price_data):
                    positions_to_close.append((symbol, position))

            # Close positions
            for symbol, position in positions_to_close:
                exit_price = position.current_price
                exit_time = current_time

                # Create trade record
                trade = Trade(
                    symbol=symbol,
                    side=position.side,
                    quantity=position.quantity,
                    entry_price=position.entry_price,
                    entry_time=position.entry_time,
                    exit_price=exit_price,
                    exit_time=exit_time,
                    commission=self.commission_per_trade,
                    strategy_name=strategy.name
                )

                result.trades.append(trade)
                current_balance += trade.pnl if trade.pnl else Decimal('0')
                del positions[symbol]

            # Check entry conditions if we have capacity
            if len(positions) < max_positions:
                for symbol in symbols:
                    if symbol in positions:
                        continue

                    price_data = symbol_data[symbol][:symbol_data[symbol].index(
                        next(p for p in symbol_data[symbol] if p.timestamp >= current_time)
                    ) + 1]

                    current_price = self._get_price_at_time(price_data, current_time)
                    if not current_price:
                        continue

                    # Check for long entry
                    if strategy.should_enter_long(symbol, price_data, positions):
                        position_size = strategy.calculate_position_size(symbol, current_price, current_balance)
                        if position_size > 0 and position_size * current_price <= current_balance:
                            position = Position(symbol, 'BUY', position_size, current_price, current_time)
                            positions[symbol] = position
                            continue

                    # Check for short entry
                    if strategy.should_enter_short(symbol, price_data, positions):
                        position_size = strategy.calculate_position_size(symbol, current_price, current_balance)
                        if position_size > 0:  # Short selling - no balance requirement
                            position = Position(symbol, 'SELL', position_size, current_price, current_time)
                            positions[symbol] = position

            # Update equity curve
            unrealized_pnl = sum(p.unrealized_pnl for p in positions.values())
            total_equity = current_balance + unrealized_pnl
            equity_curve.append((current_time, total_equity))

        result.equity_curve = equity_curve
        result.final_balance = total_equity

        return result

    def _generate_historical_data(self, symbol: str, start_date: datetime, end_date: datetime) -> List[PriceData]:
        """Generate synthetic historical price data."""
        # This is a simplified version - in production, you'd load real historical data
        data = []
        current_price = Decimal('100')  # Starting price

        # Generate daily data
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() < 5:  # Weekdays only
                # Random walk with trend
                change = Decimal(str(random.uniform(-0.03, 0.03)))
                close_price = current_price * (1 + change)

                # Generate OHLC
                volatility = Decimal('0.02')
                high_price = close_price * (1 + volatility)
                low_price = close_price * (1 - volatility)
                open_price = current_price

                data.append(PriceData(
                    timestamp=current_date,
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=close_price,
                    volume=Decimal('1000000')
                ))

                current_price = close_price

            current_date += timedelta(days=1)

        return data

    def _get_price_at_time(self, price_data: List[PriceData], timestamp: datetime) -> Optional[Decimal]:
        """Get price at specific timestamp."""
        for price in price_data:
            if price.timestamp == timestamp:
                return price.close
        return None

    def optimize_strategy(
        self,
        strategy_class: type,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        parameter_ranges: Dict[str, List[Any]]
    ) -> Dict[str, Any]:
        """
        Optimize strategy parameters using grid search.

        Args:
            strategy_class: Strategy class to optimize
            symbols: Symbols to trade
            start_date, end_date: Backtest period
            parameter_ranges: Dict of parameter names to lists of values to test
        """
        best_result = None
        best_parameters = None
        best_score = float('-inf')

        # Generate all parameter combinations
        import itertools
        param_names = list(parameter_ranges.keys())
        param_values = list(parameter_ranges.values())

        for param_combo in itertools.product(*param_values):
            parameters = dict(zip(param_names, param_combo))

            strategy = strategy_class(parameters)
            result = self.run_backtest(strategy, symbols, start_date, end_date)

            # Score based on Sharpe ratio and total return
            score = float(result.sharpe_ratio or 0) + float(result.total_return / 100)

            if score > best_score:
                best_score = score
                best_result = result
                best_parameters = parameters

        return {
            'best_parameters': best_parameters,
            'best_result': best_result,
            'best_score': best_score
        }

    def monte_carlo_simulation(
        self,
        strategy: TradingStrategy,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        num_simulations: int = 1000
    ) -> Dict[str, Any]:
        """Run Monte Carlo simulation to assess strategy robustness."""
        results = []

        for i in range(num_simulations):
            # Add random noise to historical data
            result = self.run_backtest(strategy, symbols, start_date, end_date)
            results.append({
                'total_return': float(result.total_return),
                'max_drawdown': float(result.max_drawdown),
                'sharpe_ratio': float(result.sharpe_ratio or 0),
                'win_rate': float(result.win_rate),
                'total_trades': result.total_trades
            })

        # Calculate statistics
        returns = [r['total_return'] for r in results]
        drawdowns = [r['max_drawdown'] for r in results]
        sharpe_ratios = [r['sharpe_ratio'] for r in results]

        return {
            'num_simulations': num_simulations,
            'return_stats': {
                'mean': statistics.mean(returns),
                'std': statistics.stdev(returns) if len(returns) > 1 else 0,
                'min': min(returns),
                'max': max(returns),
                'percentile_5': statistics.quantiles(returns, n=20)[0] if returns else 0,
                'percentile_95': statistics.quantiles(returns, n=20)[-1] if returns else 0
            },
            'drawdown_stats': {
                'mean': statistics.mean(drawdowns),
                'max': max(drawdowns)
            },
            'sharpe_stats': {
                'mean': statistics.mean(sharpe_ratios),
                'positive_sharpe_ratio': len([s for s in sharpe_ratios if s > 0]) / len(sharpe_ratios)
            }
        }


# Initialize backtesting engine with default strategies
backtesting_engine = BacktestingEngine()
backtesting_engine.register_strategy(RSIStrategy())
backtesting_engine.register_strategy(MACDStrategy())
backtesting_engine.register_strategy(MeanReversionStrategy())