"""
Advanced Analytics Service

Provides comprehensive trading analytics, performance metrics, and data visualization.
"""

import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text, desc, func, and_, or_
import statistics
import logging

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Service for advanced trading analytics and performance metrics.

    Provides detailed analysis of trading performance, risk metrics,
    market analysis, and predictive insights.
    """

    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL', 'postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense')
        self.engine = create_engine(self.database_url, echo=False)

    def get_portfolio_performance(self, user_id: str, timeframe: str = 'all') -> Dict:
        """
        Get comprehensive portfolio performance analytics.

        Args:
            user_id: User ID to analyze
            timeframe: 'all', 'month', 'quarter', 'year'

        Returns:
            Detailed portfolio performance metrics
        """
        with Session(self.engine) as session:
            try:
                # Calculate date filter
                date_filter = self._get_date_filter(timeframe)

                # Get portfolio data
                portfolio_data = session.execute(text("""
                    SELECT
                        c.id as challenge_id,
                        c.initial_balance,
                        c.current_equity,
                        c.status,
                        c.started_at,
                        c.ended_at,
                        COUNT(t.id) as trade_count,
                        COALESCE(SUM(t.realized_pnl), 0) as total_pnl,
                        COALESCE(AVG(t.realized_pnl), 0) as avg_trade_pnl,
                        COALESCE(STDDEV(t.realized_pnl), 0) as pnl_volatility,
                        MIN(t.executed_at) as first_trade,
                        MAX(t.executed_at) as last_trade
                    FROM challenges c
                    LEFT JOIN trades t ON c.id = t.challenge_id
                    WHERE c.user_id = :user_id
                    AND (c.started_at >= :date_filter OR :date_filter IS NULL)
                    GROUP BY c.id, c.initial_balance, c.current_equity, c.status, c.started_at, c.ended_at
                    ORDER BY c.started_at DESC
                """), {'user_id': user_id, 'date_filter': date_filter}).fetchall()

                if not portfolio_data:
                    return self._get_empty_portfolio_data()

                # Calculate aggregated metrics
                total_invested = sum(float(p.initial_balance) for p in portfolio_data)
                total_equity = sum(float(p.current_equity) for p in portfolio_data)
                total_pnl = sum(float(p.total_pnl) for p in portfolio_data)

                active_challenges = [p for p in portfolio_data if p.status == 'ACTIVE']
                completed_challenges = [p for p in portfolio_data if p.status in ['FUNDED', 'FAILED']]

                # Calculate returns
                total_return_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0

                # Risk metrics
                pnl_values = [float(p.total_pnl) for p in portfolio_data if p.total_pnl]
                volatility = statistics.stdev(pnl_values) if len(pnl_values) > 1 else 0

                # Sharpe ratio (simplified)
                risk_free_rate = 0.02  # 2% annual
                if volatility > 0:
                    sharpe_ratio = (total_return_pct/100 - risk_free_rate) / (volatility / total_invested)
                else:
                    sharpe_ratio = 0

                # Win rate
                winning_trades = sum(1 for p in portfolio_data if p.total_pnl and p.total_pnl > 0)
                total_trades = sum(p.trade_count for p in portfolio_data)
                win_rate = (winning_trades / len(portfolio_data) * 100) if portfolio_data else 0

                # Best and worst performers
                best_challenge = max(portfolio_data, key=lambda x: x.total_pnl or 0, default=None)
                worst_challenge = min(portfolio_data, key=lambda x: x.total_pnl or 0, default=None)

                return {
                    'overview': {
                        'total_invested': total_invested,
                        'total_equity': total_equity,
                        'total_pnl': total_pnl,
                        'total_return_pct': round(total_return_pct, 2),
                        'total_challenges': len(portfolio_data),
                        'active_challenges': len(active_challenges),
                        'completed_challenges': len(completed_challenges)
                    },
                    'performance': {
                        'sharpe_ratio': round(sharpe_ratio, 2),
                        'volatility': round(volatility, 2),
                        'win_rate': round(win_rate, 1),
                        'avg_trade_pnl': round(sum(float(p.avg_trade_pnl) for p in portfolio_data) / len(portfolio_data), 2) if portfolio_data else 0,
                        'best_challenge_pnl': float(best_challenge.total_pnl) if best_challenge else 0,
                        'worst_challenge_pnl': float(worst_challenge.total_pnl) if worst_challenge else 0
                    },
                    'risk_metrics': {
                        'max_drawdown': self._calculate_max_drawdown(portfolio_data),
                        'value_at_risk': self._calculate_var(portfolio_data),
                        'expected_shortfall': self._calculate_expected_shortfall(portfolio_data)
                    },
                    'time_series': self._get_portfolio_time_series(session, user_id, timeframe),
                    'challenges': [{
                        'id': str(p.challenge_id),
                        'initial_balance': float(p.initial_balance),
                        'current_equity': float(p.current_equity),
                        'pnl': float(p.total_pnl),
                        'return_pct': round(float(p.total_pnl) / float(p.initial_balance) * 100, 2) if p.initial_balance else 0,
                        'trade_count': p.trade_count,
                        'status': p.status,
                        'started_at': p.started_at.isoformat() if p.started_at else None,
                        'ended_at': p.ended_at.isoformat() if p.ended_at else None
                    } for p in portfolio_data[:10]]  # Top 10 challenges
                }

            except Exception as e:
                logger.error(f"Error getting portfolio performance for {user_id}: {e}")
                return self._get_empty_portfolio_data()

    def _get_empty_portfolio_data(self) -> Dict:
        """Return empty portfolio structure."""
        return {
            'overview': {'total_invested': 0, 'total_equity': 0, 'total_pnl': 0, 'total_return_pct': 0,
                        'total_challenges': 0, 'active_challenges': 0, 'completed_challenges': 0},
            'performance': {'sharpe_ratio': 0, 'volatility': 0, 'win_rate': 0, 'avg_trade_pnl': 0,
                          'best_challenge_pnl': 0, 'worst_challenge_pnl': 0},
            'risk_metrics': {'max_drawdown': 0, 'value_at_risk': 0, 'expected_shortfall': 0},
            'time_series': [],
            'challenges': []
        }

    def _calculate_max_drawdown(self, portfolio_data: List) -> float:
        """Calculate maximum drawdown from portfolio data."""
        if not portfolio_data:
            return 0

        peak = float(portfolio_data[0].current_equity)
        max_drawdown = 0

        for p in portfolio_data:
            current = float(p.current_equity)
            if current > peak:
                peak = current
            drawdown = (peak - current) / peak * 100
            max_drawdown = max(max_drawdown, drawdown)

        return round(max_drawdown, 2)

    def _calculate_var(self, portfolio_data: List, confidence: float = 0.95) -> float:
        """Calculate Value at Risk (VaR) at given confidence level."""
        pnl_values = [float(p.total_pnl) for p in portfolio_data if p.total_pnl]
        if len(pnl_values) < 2:
            return 0

        pnl_values.sort()
        index = int((1 - confidence) * len(pnl_values))
        var = pnl_values[index]

        return round(abs(var), 2)

    def _calculate_expected_shortfall(self, portfolio_data: List, confidence: float = 0.95) -> float:
        """Calculate Expected Shortfall (CVaR) beyond VaR."""
        pnl_values = [float(p.total_pnl) for p in portfolio_data if p.total_pnl]
        if len(pnl_values) < 2:
            return 0

        pnl_values.sort()
        index = int((1 - confidence) * len(pnl_values))
        tail_losses = pnl_values[:index + 1]

        if tail_losses:
            es = sum(tail_losses) / len(tail_losses)
            return round(abs(es), 2)

        return 0

    def _get_portfolio_time_series(self, session: Session, user_id: str, timeframe: str) -> List[Dict]:
        """Get portfolio value over time for charting."""
        try:
            # Get daily portfolio values
            date_filter = self._get_date_filter(timeframe)

            daily_values = session.execute(text("""
                SELECT
                    DATE(t.executed_at) as trade_date,
                    SUM(c.current_equity) as portfolio_value,
                    SUM(t.realized_pnl) as daily_pnl
                FROM challenges c
                LEFT JOIN trades t ON c.id = t.challenge_id
                WHERE c.user_id = :user_id
                AND (t.executed_at >= :date_filter OR :date_filter IS NULL)
                GROUP BY DATE(t.executed_at)
                ORDER BY trade_date
            """), {'user_id': user_id, 'date_filter': date_filter}).fetchall()

            return [{
                'date': dv.trade_date.isoformat(),
                'portfolio_value': float(dv.portfolio_value or 0),
                'daily_pnl': float(dv.daily_pnl or 0)
            } for dv in daily_values]

        except Exception as e:
            logger.error(f"Error getting portfolio time series for {user_id}: {e}")
            return []

    def get_trade_analytics(self, user_id: str, timeframe: str = 'all') -> Dict:
        """
        Get detailed trade analytics and patterns.

        Args:
            user_id: User ID to analyze
            timeframe: Time period for analysis

        Returns:
            Comprehensive trade analytics
        """
        with Session(self.engine) as session:
            try:
                date_filter = self._get_date_filter(timeframe)

                # Get trade data with patterns
                trade_data = session.execute(text("""
                    SELECT
                        t.symbol,
                        t.side,
                        t.quantity,
                        t.price,
                        t.realized_pnl,
                        t.executed_at,
                        EXTRACT(HOUR FROM t.executed_at) as trade_hour,
                        EXTRACT(DOW FROM t.executed_at) as trade_day,
                        c.initial_balance,
                        c.current_equity
                    FROM trades t
                    JOIN challenges c ON t.challenge_id = c.id
                    WHERE c.user_id = :user_id
                    AND (t.executed_at >= :date_filter OR :date_filter IS NULL)
                    ORDER BY t.executed_at DESC
                """), {'user_id': user_id, 'date_filter': date_filter}).fetchall()

                if not trade_data:
                    return self._get_empty_trade_analytics()

                # Analyze trade patterns
                symbols_performance = {}
                hourly_performance = {}
                daily_performance = {}
                pnl_distribution = []

                for trade in trade_data:
                    pnl = float(trade.realized_pnl)
                    pnl_distribution.append(pnl)

                    # Symbol performance
                    symbol = trade.symbol
                    if symbol not in symbols_performance:
                        symbols_performance[symbol] = {'trades': 0, 'pnl': 0, 'wins': 0}
                    symbols_performance[symbol]['trades'] += 1
                    symbols_performance[symbol]['pnl'] += pnl
                    if pnl > 0:
                        symbols_performance[symbol]['wins'] += 1

                    # Hourly performance
                    hour = int(trade.trade_hour)
                    if hour not in hourly_performance:
                        hourly_performance[hour] = {'trades': 0, 'pnl': 0}
                    hourly_performance[hour]['trades'] += 1
                    hourly_performance[hour]['pnl'] += pnl

                    # Daily performance
                    day = int(trade.trade_day)
                    if day not in daily_performance:
                        daily_performance[day] = {'trades': 0, 'pnl': 0}
                    daily_performance[day]['trades'] += 1
                    daily_performance[day]['pnl'] += pnl

                # Calculate metrics
                total_trades = len(trade_data)
                winning_trades = len([t for t in trade_data if t.realized_pnl > 0])
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

                # Best performing symbols
                best_symbols = sorted(symbols_performance.items(),
                                    key=lambda x: x[1]['pnl'], reverse=True)[:5]

                # Best trading hours
                best_hours = sorted(hourly_performance.items(),
                                  key=lambda x: x[1]['pnl'] / x[1]['trades'] if x[1]['trades'] > 0 else 0,
                                  reverse=True)[:5]

                return {
                    'summary': {
                        'total_trades': total_trades,
                        'winning_trades': winning_trades,
                        'losing_trades': total_trades - winning_trades,
                        'win_rate': round(win_rate, 1),
                        'total_pnl': sum(float(t.realized_pnl) for t in trade_data),
                        'avg_trade_pnl': statistics.mean(pnl_distribution) if pnl_distribution else 0,
                        'median_trade_pnl': statistics.median(pnl_distribution) if pnl_distribution else 0,
                        'pnl_std_dev': statistics.stdev(pnl_distribution) if len(pnl_distribution) > 1 else 0
                    },
                    'symbols': [{
                        'symbol': symbol,
                        'trades': data['trades'],
                        'total_pnl': data['pnl'],
                        'win_rate': round(data['wins'] / data['trades'] * 100, 1) if data['trades'] > 0 else 0,
                        'avg_pnl': round(data['pnl'] / data['trades'], 2) if data['trades'] > 0 else 0
                    } for symbol, data in best_symbols],
                    'timing': {
                        'best_hours': [{
                            'hour': hour,
                            'trades': data['trades'],
                            'avg_pnl': round(data['pnl'] / data['trades'], 2) if data['trades'] > 0 else 0
                        } for hour, data in best_hours],
                        'daily_pattern': [{
                            'day': day,
                            'trades': data['trades'],
                            'avg_pnl': round(data['pnl'] / data['trades'], 2) if data['trades'] > 0 else 0
                        } for day, data in sorted(daily_performance.items())]
                    },
                    'distribution': {
                        'pnl_histogram': self._create_pnl_histogram(pnl_distribution),
                        'trade_size_distribution': self._analyze_trade_sizes(trade_data)
                    },
                    'recent_trades': [{
                        'symbol': t.symbol,
                        'side': t.side,
                        'quantity': float(t.quantity),
                        'price': float(t.price),
                        'pnl': float(t.realized_pnl),
                        'executed_at': t.executed_at.isoformat()
                    } for t in trade_data[:20]]  # Last 20 trades
                }

            except Exception as e:
                logger.error(f"Error getting trade analytics for {user_id}: {e}")
                return self._get_empty_trade_analytics()

    def _get_empty_trade_analytics(self) -> Dict:
        """Return empty trade analytics structure."""
        return {
            'summary': {'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
                       'win_rate': 0, 'total_pnl': 0, 'avg_trade_pnl': 0,
                       'median_trade_pnl': 0, 'pnl_std_dev': 0},
            'symbols': [],
            'timing': {'best_hours': [], 'daily_pattern': []},
            'distribution': {'pnl_histogram': [], 'trade_size_distribution': []},
            'recent_trades': []
        }

    def _create_pnl_histogram(self, pnl_values: List[float], bins: int = 10) -> List[Dict]:
        """Create histogram data for PnL distribution."""
        if not pnl_values:
            return []

        min_pnl, max_pnl = min(pnl_values), max(pnl_values)
        if min_pnl == max_pnl:
            return [{'range': f'${min_pnl:.2f}', 'count': len(pnl_values)}]

        bin_width = (max_pnl - min_pnl) / bins

        histogram = []
        for i in range(bins):
            bin_start = min_pnl + (i * bin_width)
            bin_end = min_pnl + ((i + 1) * bin_width)
            count = len([p for p in pnl_values if bin_start <= p < bin_end])
            if count > 0:
                histogram.append({
                    'range': f'${bin_start:.2f} - ${bin_end:.2f}',
                    'count': count
                })

        return histogram

    def _analyze_trade_sizes(self, trade_data: List) -> List[Dict]:
        """Analyze distribution of trade sizes."""
        sizes = [float(t.quantity * t.price) for t in trade_data]
        if not sizes:
            return []

        # Create size buckets
        size_buckets = {
            'Small (< $100)': len([s for s in sizes if s < 100]),
            'Medium ($100 - $1000)': len([s for s in sizes if 100 <= s < 1000]),
            'Large ($1000 - $10000)': len([s for s in sizes if 1000 <= s < 10000]),
            'XL (≥ $10000)': len([s for s in sizes if s >= 10000])
        }

        return [{'size_range': k, 'count': v} for k, v in size_buckets.items() if v > 0]

    def get_market_analysis(self, symbols: List[str] = None) -> Dict:
        """
        Get market analysis and trends across the platform.

        Args:
            symbols: List of symbols to analyze (optional)

        Returns:
            Market analysis data
        """
        with Session(self.engine) as session:
            try:
                # Get popular symbols
                symbol_stats = session.execute(text("""
                    SELECT
                        t.symbol,
                        COUNT(*) as trade_count,
                        SUM(t.realized_pnl) as total_pnl,
                        AVG(t.realized_pnl) as avg_pnl,
                        COUNT(CASE WHEN t.realized_pnl > 0 THEN 1 END) as winning_trades
                    FROM trades t
                    GROUP BY t.symbol
                    ORDER BY trade_count DESC
                    LIMIT 20
                """)).fetchall()

                # Get market sentiment
                market_sentiment = session.execute(text("""
                    SELECT
                        DATE(t.executed_at) as trade_date,
                        SUM(CASE WHEN t.realized_pnl > 0 THEN 1 ELSE 0 END) as bullish_trades,
                        SUM(CASE WHEN t.realized_pnl < 0 THEN 1 ELSE 0 END) as bearish_trades,
                        COUNT(*) as total_trades
                    FROM trades t
                    WHERE t.executed_at >= CURRENT_DATE - INTERVAL '30 days'
                    GROUP BY DATE(t.executed_at)
                    ORDER BY trade_date DESC
                    LIMIT 30
                """)).fetchall()

                return {
                    'popular_symbols': [{
                        'symbol': s.symbol,
                        'trade_count': s.trade_count,
                        'total_pnl': float(s.total_pnl or 0),
                        'avg_pnl': round(float(s.avg_pnl or 0), 2),
                        'win_rate': round(s.winning_trades / s.trade_count * 100, 1) if s.trade_count > 0 else 0
                    } for s in symbol_stats],
                    'market_sentiment': [{
                        'date': ms.trade_date.isoformat(),
                        'bullish_ratio': round(ms.bullish_trades / ms.total_trades * 100, 1) if ms.total_trades > 0 else 0,
                        'total_trades': ms.total_trades
                    } for ms in market_sentiment],
                    'market_summary': {
                        'total_symbols_traded': len(symbol_stats),
                        'total_market_trades': sum(s.trade_count for s in symbol_stats),
                        'market_avg_win_rate': round(statistics.mean([
                            s.winning_trades / s.trade_count * 100 for s in symbol_stats if s.trade_count > 0
                        ]), 1) if symbol_stats else 0
                    }
                }

            except Exception as e:
                logger.error(f"Error getting market analysis: {e}")
                return {
                    'popular_symbols': [],
                    'market_sentiment': [],
                    'market_summary': {'total_symbols_traded': 0, 'total_market_trades': 0, 'market_avg_win_rate': 0}
                }

    def _get_date_filter(self, timeframe: str) -> Optional[datetime]:
        """Get datetime filter based on timeframe."""
        now = datetime.now(timezone.utc)

        if timeframe == 'month':
            return now - timedelta(days=30)
        elif timeframe == 'quarter':
            return now - timedelta(days=90)
        elif timeframe == 'year':
            return now - timedelta(days=365)
        else:  # 'all'
            return None


# Global analytics service instance
analytics_service = AnalyticsService()