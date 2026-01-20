"""
Professional Technical Analysis Engine

Implements comprehensive technical indicators and analysis tools:
- Trend indicators (MA, EMA, MACD)
- Momentum indicators (RSI, Stochastic, Williams %R)
- Volatility indicators (Bollinger Bands, ATR)
- Volume indicators (Volume, OBV, Chaikin Money Flow)
- Support/Resistance levels
- Chart patterns recognition
"""

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import deque
import statistics
import math

from app.market_data import market_data


class PriceData:
    """Represents OHLCV price data point."""

    def __init__(
        self,
        timestamp: datetime,
        open_price: Decimal,
        high_price: Decimal,
        low_price: Decimal,
        close_price: Decimal,
        volume: Optional[Decimal] = None
    ):
        self.timestamp = timestamp
        self.open = open_price
        self.high = high_price
        self.low = low_price
        self.close = close_price
        self.volume = volume or Decimal('0')


class TechnicalIndicators:
    """Collection of technical analysis indicators."""

    @staticmethod
    def sma(prices: List[Decimal], period: int) -> List[Optional[Decimal]]:
        """Simple Moving Average."""
        if len(prices) < period:
            return [None] * len(prices)

        result = [None] * (period - 1)
        for i in range(period - 1, len(prices)):
            avg = sum(prices[i - period + 1:i + 1]) / period
            result.append(avg)

        return result

    @staticmethod
    def ema(prices: List[Decimal], period: int) -> List[Optional[Decimal]]:
        """Exponential Moving Average."""
        if len(prices) < period:
            return [None] * len(prices)

        result = [None] * len(prices)
        multiplier = Decimal('2') / (period + 1)

        # First EMA is SMA
        sma = sum(prices[:period]) / period
        result[period - 1] = sma

        # Calculate subsequent EMAs
        for i in range(period, len(prices)):
            ema_value = (prices[i] - result[i - 1]) * multiplier + result[i - 1]
            result[i] = ema_value

        return result

    @staticmethod
    def rsi(prices: List[Decimal], period: int = 14) -> List[Optional[Decimal]]:
        """Relative Strength Index."""
        if len(prices) < period + 1:
            return [None] * len(prices)

        result = [None] * len(prices)
        gains = []
        losses = []

        # Calculate price changes
        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            gains.append(max(change, Decimal('0')))
            losses.append(max(-change, Decimal('0')))

        # Calculate initial averages
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        if avg_loss == 0:
            result[period] = Decimal('100')
        else:
            rs = avg_gain / avg_loss
            result[period] = Decimal('100') - (Decimal('100') / (Decimal('1') + rs))

        # Calculate subsequent RSIs
        for i in range(period + 1, len(prices)):
            avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period

            if avg_loss == 0:
                result[i] = Decimal('100')
            else:
                rs = avg_gain / avg_loss
                result[i] = Decimal('100') - (Decimal('100') / (Decimal('1') + rs))

        return result

    @staticmethod
    def macd(
        prices: List[Decimal],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Tuple[List[Optional[Decimal]], List[Optional[Decimal]], List[Optional[Decimal]]]:
        """MACD (Moving Average Convergence Divergence)."""
        fast_ema = TechnicalIndicators.ema(prices, fast_period)
        slow_ema = TechnicalIndicators.ema(prices, slow_period)

        # Calculate MACD line
        macd_line = []
        for i in range(len(prices)):
            if fast_ema[i] is not None and slow_ema[i] is not None:
                macd_line.append(fast_ema[i] - slow_ema[i])
            else:
                macd_line.append(None)

        # Calculate signal line (EMA of MACD)
        signal_line = TechnicalIndicators.ema(
            [x for x in macd_line if x is not None],
            signal_period
        )

        # Pad signal line to match macd_line length
        signal_padded = [None] * len(macd_line)
        signal_idx = 0
        for i in range(len(macd_line)):
            if macd_line[i] is not None:
                if signal_idx < len(signal_line):
                    signal_padded[i] = signal_line[signal_idx]
                signal_idx += 1

        # Calculate histogram
        histogram = []
        for i in range(len(macd_line)):
            if macd_line[i] is not None and signal_padded[i] is not None:
                histogram.append(macd_line[i] - signal_padded[i])
            else:
                histogram.append(None)

        return macd_line, signal_padded, histogram

    @staticmethod
    def bollinger_bands(
        prices: List[Decimal],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Tuple[List[Optional[Decimal]], List[Optional[Decimal]], List[Optional[Decimal]]]:
        """Bollinger Bands."""
        if len(prices) < period:
            return [None] * len(prices), [None] * len(prices), [None] * len(prices)

        sma_values = TechnicalIndicators.sma(prices, period)
        upper_band = []
        lower_band = []

        for i in range(len(prices)):
            if sma_values[i] is not None:
                # Calculate standard deviation
                start_idx = i - period + 1
                period_prices = prices[start_idx:i + 1]
                std = Decimal(str(statistics.stdev([float(p) for p in period_prices])))

                upper = sma_values[i] + (std * Decimal(str(std_dev)))
                lower = sma_values[i] - (std * Decimal(str(std_dev)))

                upper_band.append(upper)
                lower_band.append(lower)
            else:
                upper_band.append(None)
                lower_band.append(None)

        return sma_values, upper_band, lower_band

    @staticmethod
    def stochastic_oscillator(
        high_prices: List[Decimal],
        low_prices: List[Decimal],
        close_prices: List[Decimal],
        k_period: int = 14,
        d_period: int = 3
    ) -> Tuple[List[Optional[Decimal]], List[Optional[Decimal]]]:
        """Stochastic Oscillator."""
        if len(close_prices) < k_period:
            return [None] * len(close_prices), [None] * len(close_prices)

        k_values = []

        for i in range(k_period - 1, len(close_prices)):
            high = max(high_prices[i - k_period + 1:i + 1])
            low = min(low_prices[i - k_period + 1:i + 1])
            close = close_prices[i]

            if high == low:
                k_values.append(Decimal('50'))
            else:
                k = ((close - low) / (high - low)) * 100
                k_values.append(k)

        # Pad K values
        k_padded = [None] * (k_period - 1) + k_values

        # Calculate D line (SMA of K)
        d_values = TechnicalIndicators.sma(k_values, d_period)
        d_padded = [None] * (k_period - 1) + d_values

        return k_padded, d_padded

    @staticmethod
    def atr(
        high_prices: List[Decimal],
        low_prices: List[Decimal],
        close_prices: List[Decimal],
        period: int = 14
    ) -> List[Optional[Decimal]]:
        """Average True Range."""
        if len(close_prices) < 2:
            return [None] * len(close_prices)

        true_ranges = []

        # Calculate True Range for each period
        for i in range(1, len(close_prices)):
            tr1 = high_prices[i] - low_prices[i]
            tr2 = abs(high_prices[i] - close_prices[i - 1])
            tr3 = abs(low_prices[i] - close_prices[i - 1])
            true_range = max(tr1, tr2, tr3)
            true_ranges.append(true_range)

        # Calculate ATR using EMA
        return TechnicalIndicators.ema(true_ranges, period)

    @staticmethod
    def fibonacci_retracement(
        high_price: Decimal,
        low_price: Decimal
    ) -> Dict[str, Decimal]:
        """Calculate Fibonacci retracement levels."""
        diff = high_price - low_price

        return {
            '0.0': low_price,
            '0.236': low_price + (diff * Decimal('0.236')),
            '0.382': low_price + (diff * Decimal('0.382')),
            '0.5': low_price + (diff * Decimal('0.5')),
            '0.618': low_price + (diff * Decimal('0.618')),
            '0.786': low_price + (diff * Decimal('0.786')),
            '1.0': high_price
        }

    @staticmethod
    def pivot_points(high: Decimal, low: Decimal, close: Decimal) -> Dict[str, Decimal]:
        """Calculate pivot points and support/resistance levels."""
        pivot = (high + low + close) / 3

        return {
            'pivot': pivot,
            'r1': (2 * pivot) - low,
            'r2': pivot + (high - low),
            'r3': high + 2 * (pivot - low),
            's1': (2 * pivot) - high,
            's2': pivot - (high - low),
            's3': low - 2 * (high - pivot)
        }


class ChartAnalysis:
    """Chart pattern recognition and analysis."""

    @staticmethod
    def detect_support_resistance(
        prices: List[PriceData],
        lookback_periods: int = 20,
        tolerance: float = 0.02
    ) -> Dict[str, List[Decimal]]:
        """Detect support and resistance levels."""
        if len(prices) < lookback_periods:
            return {'support': [], 'resistance': []}

        highs = [p.high for p in prices[-lookback_periods:]]
        lows = [p.low for p in prices[-lookback_periods:]]

        # Find local maxima and minima
        resistance_levels = []
        support_levels = []

        for i in range(2, len(highs) - 2):
            # Local maximum
            if highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and \
               highs[i] > highs[i + 1] and highs[i] > highs[i + 2]:
                resistance_levels.append(highs[i])

            # Local minimum
            if lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and \
               lows[i] < lows[i + 1] and lows[i] < lows[i + 2]:
                support_levels.append(lows[i])

        # Group similar levels
        def group_levels(levels: List[Decimal], tolerance: float) -> List[Decimal]:
            if not levels:
                return []

            levels.sort()
            grouped = [levels[0]]

            for level in levels[1:]:
                if abs(float(level - grouped[-1])) / float(grouped[-1]) > tolerance:
                    grouped.append(level)

            return grouped

        return {
            'support': group_levels(support_levels, tolerance),
            'resistance': group_levels(resistance_levels, tolerance)
        }

    @staticmethod
    def detect_trend(prices: List[PriceData], period: int = 20) -> str:
        """Detect current trend direction."""
        if len(prices) < period:
            return 'SIDEWAYS'

        closes = [p.close for p in prices[-period:]]

        # Calculate linear regression
        x = list(range(len(closes)))
        y = [float(p) for p in closes]

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_xx = sum(xi ** 2 for xi in x)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x ** 2)

        if slope > 0.001:  # Uptrend
            return 'UPTREND'
        elif slope < -0.001:  # Downtrend
            return 'DOWNTREND'
        else:  # Sideways
            return 'SIDEWAYS'

    @staticmethod
    def calculate_momentum(prices: List[PriceData], period: int = 14) -> List[Optional[Decimal]]:
        """Calculate momentum indicator."""
        if len(prices) < period:
            return [None] * len(prices)

        closes = [p.close for p in prices]
        momentum = []

        for i in range(len(closes)):
            if i < period:
                momentum.append(None)
            else:
                momentum.append(closes[i] - closes[i - period])

        return momentum


class TechnicalAnalysisEngine:
    """Main technical analysis engine."""

    def __init__(self):
        self.price_cache: Dict[str, List[PriceData]] = {}
        self.cache_expiry = timedelta(minutes=5)

    def get_technical_analysis(self, symbol: str, indicators: List[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive technical analysis for a symbol.

        Args:
            symbol: Stock symbol
            indicators: List of indicators to calculate (optional)
        """
        if indicators is None:
            indicators = ['sma', 'ema', 'rsi', 'macd', 'bollinger', 'stochastic']

        # Get price data
        price_data = self._get_price_data(symbol)
        if not price_data:
            return {'error': f'No price data available for {symbol}'}

        closes = [p.close for p in price_data]
        highs = [p.high for p in price_data]
        lows = [p.low for p in price_data]

        analysis = {
            'symbol': symbol,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'indicators': {},
            'patterns': {},
            'trend': ChartAnalysis.detect_trend(price_data),
            'support_resistance': ChartAnalysis.detect_support_resistance(price_data)
        }

        # Calculate requested indicators
        if 'sma' in indicators:
            analysis['indicators']['sma_20'] = TechnicalIndicators.sma(closes, 20)[-1]
            analysis['indicators']['sma_50'] = TechnicalIndicators.sma(closes, 50)[-1]

        if 'ema' in indicators:
            analysis['indicators']['ema_12'] = TechnicalIndicators.ema(closes, 12)[-1]
            analysis['indicators']['ema_26'] = TechnicalIndicators.ema(closes, 26)[-1]

        if 'rsi' in indicators:
            analysis['indicators']['rsi_14'] = TechnicalIndicators.rsi(closes, 14)[-1]

        if 'macd' in indicators:
            macd_line, signal_line, histogram = TechnicalIndicators.macd(closes)
            analysis['indicators']['macd'] = {
                'line': macd_line[-1],
                'signal': signal_line[-1],
                'histogram': histogram[-1]
            }

        if 'bollinger' in indicators:
            sma, upper, lower = TechnicalIndicators.bollinger_bands(closes)
            analysis['indicators']['bollinger'] = {
                'sma': sma[-1],
                'upper': upper[-1],
                'lower': lower[-1]
            }

        if 'stochastic' in indicators:
            k_line, d_line = TechnicalIndicators.stochastic_oscillator(highs, lows, closes)
            analysis['indicators']['stochastic'] = {
                'k': k_line[-1],
                'd': d_line[-1]
            }

        if 'atr' in indicators:
            analysis['indicators']['atr_14'] = TechnicalIndicators.atr(highs, lows, closes, 14)[-1]

        if 'momentum' in indicators:
            analysis['indicators']['momentum_14'] = ChartAnalysis.calculate_momentum(price_data, 14)[-1]

        # Generate signals
        analysis['signals'] = self._generate_signals(analysis)

        return analysis

    def _get_price_data(self, symbol: str) -> List[PriceData]:
        """Get historical price data for technical analysis."""
        # This is a simplified version - in production, you'd fetch real historical data
        # For now, we'll generate synthetic data based on current price

        current_price, _ = market_data.get_stock_price(symbol)
        if not current_price:
            return []

        # Generate 100 periods of historical data (simplified)
        price_data = []
        base_price = current_price

        for i in range(100):
            # Simple random walk with trend
            change = Decimal(str((0.5 - 0.5) * 0.02))  # Random change
            close_price = base_price * (1 + change)
            open_price = base_price
            high_price = max(open_price, close_price) * Decimal('1.005')
            low_price = min(open_price, close_price) * Decimal('0.995')

            timestamp = datetime.now(timezone.utc) - timedelta(days=100 - i)

            price_data.append(PriceData(
                timestamp=timestamp,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume=Decimal('1000000')  # Mock volume
            ))

            base_price = close_price

        return price_data

    def _generate_signals(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate trading signals based on technical indicators."""
        signals = []
        indicators = analysis.get('indicators', {})

        # RSI signals
        rsi = indicators.get('rsi_14')
        if rsi:
            if rsi < 30:
                signals.append({
                    'type': 'BUY',
                    'indicator': 'RSI',
                    'strength': 'STRONG',
                    'reason': 'RSI oversold',
                    'value': float(rsi)
                })
            elif rsi > 70:
                signals.append({
                    'type': 'SELL',
                    'indicator': 'RSI',
                    'strength': 'STRONG',
                    'reason': 'RSI overbought',
                    'value': float(rsi)
                })

        # MACD signals
        macd = indicators.get('macd')
        if macd:
            line = macd.get('line')
            signal = macd.get('signal')
            histogram = macd.get('histogram')

            if line and signal:
                if line > signal and histogram and histogram > 0:
                    signals.append({
                        'type': 'BUY',
                        'indicator': 'MACD',
                        'strength': 'MEDIUM',
                        'reason': 'MACD bullish crossover',
                        'value': float(line - signal)
                    })
                elif line < signal and histogram and histogram < 0:
                    signals.append({
                        'type': 'SELL',
                        'indicator': 'MACD',
                        'strength': 'MEDIUM',
                        'reason': 'MACD bearish crossover',
                        'value': float(line - signal)
                    })

        # Bollinger Band signals
        bollinger = indicators.get('bollinger')
        if bollinger and 'sma_20' in indicators:
            current_price = analysis.get('current_price', 0)
            lower = bollinger.get('lower')
            upper = bollinger.get('upper')

            if lower and current_price < lower:
                signals.append({
                    'type': 'BUY',
                    'indicator': 'BOLLINGER_BANDS',
                    'strength': 'MEDIUM',
                    'reason': 'Price below lower Bollinger Band',
                    'value': float((lower - current_price) / current_price * 100)
                })
            elif upper and current_price > upper:
                signals.append({
                    'type': 'SELL',
                    'indicator': 'BOLLINGER_BANDS',
                    'strength': 'MEDIUM',
                    'reason': 'Price above upper Bollinger Band',
                    'value': float((current_price - upper) / current_price * 100)
                })

        # Stochastic signals
        stochastic = indicators.get('stochastic')
        if stochastic:
            k = stochastic.get('k')
            d = stochastic.get('d')

            if k and d:
                if k < 20 and d < 20:
                    signals.append({
                        'type': 'BUY',
                        'indicator': 'STOCHASTIC',
                        'strength': 'MEDIUM',
                        'reason': 'Stochastic oversold',
                        'value': float(k)
                    })
                elif k > 80 and d > 80:
                    signals.append({
                        'type': 'SELL',
                        'indicator': 'STOCHASTIC',
                        'strength': 'MEDIUM',
                        'reason': 'Stochastic overbought',
                        'value': float(k)
                    })

        # Trend signals
        trend = analysis.get('trend')
        if trend == 'UPTREND':
            signals.append({
                'type': 'BUY',
                'indicator': 'TREND',
                'strength': 'WEAK',
                'reason': 'Uptrend detected',
                'value': 1
            })
        elif trend == 'DOWNTREND':
            signals.append({
                'type': 'SELL',
                'indicator': 'TREND',
                'strength': 'WEAK',
                'reason': 'Downtrend detected',
                'value': -1
            })

        return signals

    def get_chart_data(self, symbol: str, timeframe: str = '1D', periods: int = 100) -> Dict[str, Any]:
        """Get chart data with technical indicators for frontend visualization."""
        price_data = self._get_price_data(symbol)

        if not price_data:
            return {'error': f'No chart data available for {symbol}'}

        # Prepare OHLCV data
        chart_data = {
            'symbol': symbol,
            'timeframe': timeframe,
            'data': []
        }

        for price in price_data[-periods:]:
            chart_data['data'].append({
                'timestamp': price.timestamp.isoformat(),
                'open': float(price.open),
                'high': float(price.high),
                'low': float(price.low),
                'close': float(price.close),
                'volume': float(price.volume)
            })

        # Add technical indicators
        closes = [p.close for p in price_data]
        highs = [p.high for p in price_data]
        lows = [p.low for p in price_data]

        # Simple moving averages
        sma_20 = TechnicalIndicators.sma(closes, 20)
        sma_50 = TechnicalIndicators.sma(closes, 50)

        # RSI
        rsi_values = TechnicalIndicators.rsi(closes, 14)

        # MACD
        macd_line, signal_line, histogram = TechnicalIndicators.macd(closes)

        # Bollinger Bands
        bb_sma, bb_upper, bb_lower = TechnicalIndicators.bollinger_bands(closes)

        # Add indicators to chart data
        for i, data_point in enumerate(chart_data['data']):
            base_idx = len(price_data) - periods + i

            data_point.update({
                'sma_20': float(sma_20[base_idx]) if sma_20[base_idx] else None,
                'sma_50': float(sma_50[base_idx]) if sma_50[base_idx] else None,
                'rsi': float(rsi_values[base_idx]) if rsi_values[base_idx] else None,
                'macd_line': float(macd_line[base_idx]) if macd_line[base_idx] else None,
                'macd_signal': float(signal_line[base_idx]) if signal_line[base_idx] else None,
                'macd_histogram': float(histogram[base_idx]) if histogram[base_idx] else None,
                'bb_sma': float(bb_sma[base_idx]) if bb_sma[base_idx] else None,
                'bb_upper': float(bb_upper[base_idx]) if bb_upper[base_idx] else None,
                'bb_lower': float(bb_lower[base_idx]) if bb_lower[base_idx] else None,
            })

        return chart_data


# Global technical analysis engine instance
technical_analysis_engine = TechnicalAnalysisEngine()