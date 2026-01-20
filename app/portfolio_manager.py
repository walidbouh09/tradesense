"""
Professional Portfolio Management System

Features:
- Multi-asset position tracking
- Portfolio diversification analysis
- Risk exposure monitoring
- Performance attribution
- Rebalancing recommendations
"""

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import statistics

from app.market_data import market_data


class Position:
    """Represents a trading position in a portfolio."""

    def __init__(
        self,
        challenge_id: str,
        symbol: str,
        quantity: Decimal,
        average_cost: Decimal,
        current_price: Optional[Decimal] = None,
        entry_date: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.challenge_id = challenge_id
        self.symbol = symbol
        self.quantity = quantity
        self.average_cost = average_cost
        self.current_price = current_price or average_cost
        self.entry_date = entry_date or datetime.now(timezone.utc)
        self.last_updated = datetime.now(timezone.utc)
        self.metadata = metadata or {}

    @property
    def market_value(self) -> Decimal:
        """Current market value of the position."""
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> Decimal:
        """Unrealized profit/loss."""
        return (self.current_price - self.average_cost) * self.quantity

    @property
    def unrealized_pnl_percent(self) -> Decimal:
        """Unrealized profit/loss percentage."""
        if self.average_cost == 0:
            return Decimal('0')
        return ((self.current_price - self.average_cost) / self.average_cost) * 100

    def update_price(self, new_price: Decimal):
        """Update current price and timestamp."""
        self.current_price = new_price
        self.last_updated = datetime.now(timezone.utc)


class Portfolio:
    """Professional portfolio with multi-asset management."""

    def __init__(self, challenge_id: str, initial_balance: Decimal):
        self.challenge_id = challenge_id
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.positions: Dict[str, Position] = {}
        self.realized_pnl = Decimal('0')
        self.total_pnl = Decimal('0')
        self.created_at = datetime.now(timezone.utc)
        self.last_updated = datetime.now(timezone.utc)

    @property
    def total_value(self) -> Decimal:
        """Total portfolio value (cash + positions)."""
        positions_value = sum(pos.market_value for pos in self.positions.values())
        return self.current_balance + positions_value

    @property
    def total_unrealized_pnl(self) -> Decimal:
        """Total unrealized P&L across all positions."""
        return sum(pos.unrealized_pnl for pos in self.positions.values())

    @property
    def total_pnl(self) -> Decimal:
        """Total P&L (realized + unrealized)."""
        return self.realized_pnl + self.total_unrealized_pnl

    @property
    def return_percentage(self) -> Decimal:
        """Portfolio return percentage."""
        if self.initial_balance == 0:
            return Decimal('0')
        return ((self.total_value - self.initial_balance) / self.initial_balance) * 100

    @property
    def position_count(self) -> int:
        """Number of active positions."""
        return len([p for p in self.positions.values() if p.quantity != 0])

    @property
    def diversification_score(self) -> Decimal:
        """Portfolio diversification score (0-100)."""
        if not self.positions:
            return Decimal('100')  # Fully diversified (no positions)

        # Calculate position weights
        total_value = self.total_value
        if total_value == 0:
            return Decimal('0')

        weights = []
        for position in self.positions.values():
            if position.quantity != 0:
                weight = float(position.market_value / total_value)
                weights.append(weight)

        if len(weights) <= 1:
            return Decimal('0')  # Single position = no diversification

        # Calculate diversification score
        # Higher score = more diversified
        # Use inverse of concentration (1 - Herfindahl index)
        herfindahl = sum(w ** 2 for w in weights)
        diversification = (1 - herfindahl) * 100

        return Decimal(str(diversification)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

    @property
    def sector_exposure(self) -> Dict[str, Decimal]:
        """Sector exposure breakdown."""
        # Simplified sector mapping (in production, use proper sector data)
        sector_map = {
            'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Technology',
            'AMZN': 'Consumer', 'TSLA': 'Automotive', 'NVDA': 'Technology',
            'BCP.MA': 'Banking', 'ATL.MA': 'Telecom', 'CMA.MA': 'Mining'
        }

        exposure = defaultdict(Decimal)
        total_value = self.total_value

        for symbol, position in self.positions.items():
            if position.quantity != 0 and total_value > 0:
                sector = sector_map.get(symbol, 'Other')
                weight = (position.market_value / total_value) * 100
                exposure[sector] += weight

        return dict(exposure)

    @property
    def risk_metrics(self) -> Dict[str, Any]:
        """Portfolio risk metrics."""
        if not self.positions:
            return {
                'volatility': Decimal('0'),
                'max_drawdown': Decimal('0'),
                'sharpe_ratio': Decimal('0'),
                'beta': Decimal('1'),
                'value_at_risk_95': Decimal('0')
            }

        # Calculate volatility from position returns
        returns = []
        for position in self.positions.values():
            if position.quantity != 0:
                returns.append(float(position.unrealized_pnl_percent))

        volatility = Decimal('0')
        if returns:
            try:
                volatility = Decimal(str(statistics.stdev(returns))).quantize(Decimal('0.01'))
            except statistics.StatisticsError:
                volatility = Decimal('0')

        # Simplified risk metrics (in production, use historical data)
        return {
            'volatility': volatility,
            'max_drawdown': self._calculate_max_drawdown(),
            'sharpe_ratio': self._calculate_sharpe_ratio(),
            'beta': Decimal('1.0'),  # Market beta
            'value_at_risk_95': self._calculate_var_95()
        }

    def _calculate_max_drawdown(self) -> Decimal:
        """Calculate maximum drawdown."""
        # Simplified calculation - in production use historical data
        if not self.positions:
            return Decimal('0')

        max_dd = Decimal('0')
        for position in self.positions.values():
            if position.unrealized_pnl < 0:
                dd_percent = abs(position.unrealized_pnl_percent)
                max_dd = max(max_dd, dd_percent)

        return max_dd.quantize(Decimal('0.01'))

    def _calculate_sharpe_ratio(self) -> Decimal:
        """Calculate Sharpe ratio."""
        if not self.positions:
            return Decimal('0')

        # Simplified calculation
        avg_return = float(self.return_percentage)
        volatility = float(self.risk_metrics['volatility'])

        if volatility == 0:
            return Decimal('0')

        # Assume risk-free rate of 2%
        risk_free_rate = 2.0
        sharpe = (avg_return - risk_free_rate) / volatility

        return Decimal(str(sharpe)).quantize(Decimal('0.01'))

    def _calculate_var_95(self) -> Decimal:
        """Calculate Value at Risk (95% confidence)."""
        # Simplified VaR calculation
        portfolio_value = float(self.total_value)
        volatility = float(self.risk_metrics['volatility'])

        # Assume normal distribution
        var_95 = portfolio_value * volatility * 1.645 / 100  # 95% confidence

        return Decimal(str(var_95)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

    def add_position(self, symbol: str, quantity: Decimal, price: Decimal) -> Position:
        """Add or update a position."""
        if symbol in self.positions:
            # Update existing position
            position = self.positions[symbol]
            total_quantity = position.quantity + quantity
            total_cost = (position.quantity * position.average_cost) + (quantity * price)

            if total_quantity != 0:
                position.average_cost = total_cost / total_quantity
            position.quantity = total_quantity
            position.update_price(price)
        else:
            # Create new position
            position = Position(
                challenge_id=self.challenge_id,
                symbol=symbol,
                quantity=quantity,
                average_cost=price,
                current_price=price
            )
            self.positions[symbol] = position

        # Remove zero positions
        if position.quantity == 0:
            del self.positions[symbol]

        self.last_updated = datetime.now(timezone.utc)
        return position

    def remove_position(self, symbol: str, quantity: Optional[Decimal] = None) -> Optional[Position]:
        """Remove or reduce a position."""
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]

        if quantity is None or quantity >= position.quantity:
            # Close entire position
            del self.positions[symbol]
            return position
        else:
            # Reduce position
            position.quantity -= quantity
            return position

    def update_prices(self):
        """Update all position prices with current market data."""
        for symbol, position in self.positions.items():
            current_price, _ = market_data.get_stock_price(symbol)
            if current_price:
                position.update_price(current_price)

        self.last_updated = datetime.now(timezone.utc)

    def get_position_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all positions."""
        summary = []
        for symbol, position in self.positions.items():
            summary.append({
                'symbol': symbol,
                'quantity': float(position.quantity),
                'average_cost': float(position.average_cost),
                'current_price': float(position.current_price),
                'market_value': float(position.market_value),
                'unrealized_pnl': float(position.unrealized_pnl),
                'unrealized_pnl_percent': float(position.unrealized_pnl_percent),
                'entry_date': position.entry_date.isoformat(),
                'last_updated': position.last_updated.isoformat()
            })

        return sorted(summary, key=lambda x: x['market_value'], reverse=True)

    def get_rebalancing_recommendations(self, target_allocations: Dict[str, Decimal]) -> List[Dict[str, Any]]:
        """
        Generate rebalancing recommendations based on target allocations.

        Args:
            target_allocations: Dict of symbol -> target percentage
        """
        recommendations = []
        total_value = self.total_value

        if total_value == 0:
            return recommendations

        for symbol, target_percent in target_allocations.items():
            current_value = Decimal('0')
            if symbol in self.positions:
                current_value = self.positions[symbol].market_value

            current_percent = (current_value / total_value) * 100
            difference = target_percent - current_percent

            if abs(difference) > Decimal('1'):  # Rebalance if difference > 1%
                recommendations.append({
                    'symbol': symbol,
                    'current_allocation': float(current_percent),
                    'target_allocation': float(target_percent),
                    'difference': float(difference),
                    'action': 'BUY' if difference > 0 else 'SELL',
                    'amount': float(abs(difference) * total_value / 100)
                })

        return sorted(recommendations, key=lambda x: abs(x['difference']), reverse=True)


class PortfolioManager:
    """Central portfolio management system."""

    def __init__(self):
        self.portfolios: Dict[str, Portfolio] = {}
        self._last_price_update = datetime.now(timezone.utc)

    def get_portfolio(self, challenge_id: str, initial_balance: Optional[Decimal] = None) -> Portfolio:
        """Get or create a portfolio for a challenge."""
        if challenge_id not in self.portfolios:
            if initial_balance is None:
                initial_balance = Decimal('100000')  # Default balance
            self.portfolios[challenge_id] = Portfolio(challenge_id, initial_balance)

        return self.portfolios[challenge_id]

    def update_portfolio_from_trades(self, challenge_id: str, trades: List[Dict[str, Any]]):
        """Update portfolio from trade executions."""
        portfolio = self.get_portfolio(challenge_id)

        for trade in trades:
            symbol = trade['symbol']
            side = trade['side']
            quantity = Decimal(str(trade['quantity']))
            price = Decimal(str(trade['price']))

            # Adjust quantity based on side
            if side == 'SELL':
                quantity = -quantity

            portfolio.add_position(symbol, quantity, price)

    def get_portfolio_summary(self, challenge_id: str) -> Dict[str, Any]:
        """Get comprehensive portfolio summary."""
        portfolio = self.get_portfolio(challenge_id)

        # Update prices if needed (every 5 minutes)
        now = datetime.now(timezone.utc)
        if (now - self._last_price_update).total_seconds() > 300:
            portfolio.update_prices()
            self._last_price_update = now

        return {
            'challenge_id': challenge_id,
            'total_value': float(portfolio.total_value),
            'current_balance': float(portfolio.current_balance),
            'initial_balance': float(portfolio.initial_balance),
            'total_pnl': float(portfolio.total_pnl),
            'unrealized_pnl': float(portfolio.total_unrealized_pnl),
            'realized_pnl': float(portfolio.realized_pnl),
            'return_percentage': float(portfolio.return_percentage),
            'position_count': portfolio.position_count,
            'diversification_score': float(portfolio.diversification_score),
            'sector_exposure': portfolio.sector_exposure,
            'risk_metrics': {
                'volatility': float(portfolio.risk_metrics['volatility']),
                'max_drawdown': float(portfolio.risk_metrics['max_drawdown']),
                'sharpe_ratio': float(portfolio.risk_metrics['sharpe_ratio']),
                'beta': float(portfolio.risk_metrics['beta']),
                'value_at_risk_95': float(portfolio.risk_metrics['value_at_risk_95'])
            },
            'positions': portfolio.get_position_summary(),
            'last_updated': portfolio.last_updated.isoformat()
        }

    def get_portfolio_analytics(self, challenge_id: str) -> Dict[str, Any]:
        """Get advanced portfolio analytics."""
        portfolio = self.get_portfolio(challenge_id)

        # Calculate performance metrics
        positions = portfolio.get_position_summary()
        top_performers = sorted(positions, key=lambda x: x['unrealized_pnl_percent'], reverse=True)[:5]
        worst_performers = sorted(positions, key=lambda x: x['unrealized_pnl_percent'])[:5]

        # Calculate concentration metrics
        total_value = portfolio.total_value
        concentration = {}
        for pos in positions:
            concentration[pos['symbol']] = float(pos['market_value'] / total_value * 100) if total_value > 0 else 0

        return {
            'challenge_id': challenge_id,
            'performance': {
                'total_return': float(portfolio.return_percentage),
                'annualized_return': float(portfolio.return_percentage),  # Simplified
                'volatility': float(portfolio.risk_metrics['volatility']),
                'sharpe_ratio': float(portfolio.risk_metrics['sharpe_ratio']),
                'max_drawdown': float(portfolio.risk_metrics['max_drawdown'])
            },
            'concentration': concentration,
            'top_performers': top_performers,
            'worst_performers': worst_performers,
            'sector_analysis': portfolio.sector_exposure,
            'diversification_score': float(portfolio.diversification_score),
            'risk_assessment': self._assess_portfolio_risk(portfolio)
        }

    def _assess_portfolio_risk(self, portfolio: Portfolio) -> Dict[str, Any]:
        """Assess overall portfolio risk."""
        diversification_score = portfolio.diversification_score
        volatility = portfolio.risk_metrics['volatility']
        max_drawdown = portfolio.risk_metrics['max_drawdown']

        # Risk assessment logic
        risk_level = 'LOW'
        risk_score = 0

        if diversification_score < 30:
            risk_score += 30  # High concentration risk
        elif diversification_score < 60:
            risk_score += 15  # Moderate concentration risk

        if volatility > Decimal('20'):
            risk_score += 25  # High volatility
        elif volatility > Decimal('10'):
            risk_score += 10  # Moderate volatility

        if max_drawdown > Decimal('15'):
            risk_score += 25  # High drawdown
        elif max_drawdown > Decimal('5'):
            risk_score += 10  # Moderate drawdown

        if risk_score >= 50:
            risk_level = 'HIGH'
        elif risk_score >= 25:
            risk_level = 'MEDIUM'

        return {
            'risk_level': risk_level,
            'risk_score': int(risk_score),
            'recommendations': self._get_risk_recommendations(risk_level, portfolio)
        }

    def _get_risk_recommendations(self, risk_level: str, portfolio: Portfolio) -> List[str]:
        """Generate risk management recommendations."""
        recommendations = []

        if risk_level == 'HIGH':
            recommendations.extend([
                "Reduce position concentration by diversifying across more assets",
                "Implement stricter stop-loss orders",
                "Consider reducing position sizes",
                "Monitor volatility closely"
            ])
        elif risk_level == 'MEDIUM':
            recommendations.extend([
                "Consider adding more diversification",
                "Monitor drawdown levels",
                "Review position sizing strategy"
            ])
        else:
            recommendations.append("Portfolio risk is well-managed")

        if portfolio.position_count > 10:
            recommendations.append("Consider consolidating some positions")
        elif portfolio.position_count < 3:
            recommendations.append("Consider increasing diversification")

        return recommendations


# Global portfolio manager instance
portfolio_manager = PortfolioManager()