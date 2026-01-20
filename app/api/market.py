"""
Market Data API Endpoints

Provides access to real-time market data, overview, charts, and health monitoring.
"""

from flask import jsonify, request, current_app
from datetime import datetime, timezone
from . import api_bp
from app.market_data import market_data


@api_bp.route('/market/status', methods=['GET'])
def get_market_status():
    """
    Get current market status for different exchanges.

    Returns open/closed status for Casablanca, US, and global markets.
    """
    try:
        status = market_data.get_market_status()

        return jsonify({
            'status': status,
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting market status: {e}")
        return jsonify({'error': 'Failed to get market status'}), 500


@api_bp.route('/market/overview', methods=['GET'])
def get_market_overview():
    """
    Get comprehensive market overview with major indices and commodities.

    Returns real-time data for SPX, NASDAQ, DOW, GOLD with market strength indicator.
    Includes error handling and retry logic.
    """
    try:
        # Get market overview data with retry logic
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                overview = market_data.get_market_overview()

                if overview.get('status') == 'online':
                    return jsonify({
                        'overview': overview,
                        'success': True
                    }), 200
                elif attempt < max_retries - 1:
                    # Wait before retry
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    # Return offline data after all retries
                    return jsonify({
                        'overview': overview,
                        'success': True,
                        'message': 'Market data currently offline, showing cached/stale data'
                    }), 200

            except Exception as e:
                current_app.logger.warning(f"Market overview attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    # All retries failed
                    return jsonify({
                        'error': 'Market data service temporarily unavailable',
                        'details': str(e),
                        'offline_mode': True
                    }), 503

        # Fallback response
        return jsonify({
            'error': 'Unable to fetch market data after multiple attempts',
            'offline_mode': True
        }), 503

    except Exception as e:
        current_app.logger.error(f"Error in market overview endpoint: {e}")
        return jsonify({'error': 'Failed to get market overview'}), 500


@api_bp.route('/market/price/<ticker>', methods=['GET'])
def get_market_price(ticker: str):
    """
    Get latest available price for a ticker using yfinance.

    Constraints handled:
      - invalid ticker -> 404 with clear JSON
      - timeout (default 5s) -> 504
      - yfinance missing or provider error -> 503/500
    """
    try:
        try:
            import yfinance as yf
        except Exception as ie:
            current_app.logger.error(f"yfinance import error: {ie}")
            return jsonify({
                'error': 'Market provider unavailable (yfinance missing)',
                'details': str(ie),
                'success': False
            }), 503

        from concurrent.futures import ThreadPoolExecutor, TimeoutError

        def _fetch_price(t: str):
            # Try to fetch recent intraday first, then fallback to daily
            tk = yf.Ticker(t)
            hist = tk.history(period='1d', interval='1m')
            if hist is None or hist.empty:
                hist = tk.history(period='5d')
            if hist is None or hist.empty:
                return None
            # get last non-NaN close
            closes = hist['Close'].dropna()
            if closes.empty:
                return None
            return float(closes.iloc[-1])

        # Reasonable timeout for external call
        timeout_seconds = 5
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_fetch_price, ticker)
            try:
                price = future.result(timeout=timeout_seconds)
            except TimeoutError:
                return jsonify({
                    'error': 'Market data request timed out',
                    'ticker': ticker,
                    'success': False
                }), 504

        if price is None:
            return jsonify({
                'error': 'Ticker not found or no price data',
                'ticker': ticker,
                'success': False
            }), 404

        return jsonify({
            'ticker': ticker.upper(),
            'price': round(price, 6),
            'currency': 'USD',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching price for {ticker}: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to fetch market price',
            'details': str(e),
            'ticker': ticker,
            'success': False
        }), 500


@api_bp.route('/market/history/<symbol>', methods=['GET'])
def get_market_history(symbol: str):
    """
    Get historical market data for a symbol.

    Query parameters:
    - period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max (default: 1mo)
    - interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo (default: 1d)

    Supported symbols: ^GSPC (S&P 500), ^IXIC (NASDAQ), ^DJI (Dow Jones), GC=F (Gold)

    Returns data formatted for TradingView Lightweight Charts.
    """
    try:
        # Get query parameters
        period = request.args.get('period', '1mo')
        interval = request.args.get('interval', '1d')

        # Validate parameters
        valid_periods = ['1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max']
        valid_intervals = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo']

        if period not in valid_periods:
            return jsonify({
                'error': f'Invalid period. Must be one of: {", ".join(valid_periods)}',
                'success': False
            }), 400

        if interval not in valid_intervals:
            return jsonify({
                'error': f'Invalid interval. Must be one of: {", ".join(valid_intervals)}',
                'success': False
            }), 400

        # Fetch historical data using market data service
        result = market_data.get_history(symbol, period, interval)

        if result.get('success'):
            return jsonify(result), 200
        else:
            # Return error response
            status_code = 404 if 'No historical data' in result.get('error', '') else 503
            return jsonify(result), status_code

    except Exception as e:
        current_app.logger.error(f"Error in market history endpoint for {symbol}: {e}", exc_info=True)
        return jsonify({
            'error': f'Failed to get market history: {str(e)}',
            'symbol': symbol,
            'success': False
        }), 500


@api_bp.route('/market/chart/<symbol>', methods=['GET'])
def get_chart_data(symbol: str):
    """
    Legacy endpoint - redirects to /market/history/<symbol>
    """
    return get_market_history(symbol)


@api_bp.route('/market/health', methods=['GET'])
def get_market_health():
    """
    Get market data service health status.

    Returns connectivity status and last update times.
    """
    try:
        # Test market data service connectivity
        test_symbols = ['AAPL', '^GSPC', 'GC=F']
        health_status = {}

        for symbol in test_symbols:
            try:
                price, prev = market_data.get_stock_price(symbol)
                health_status[symbol] = {
                    'status': 'online' if price is not None else 'degraded',
                    'last_test': datetime.now(timezone.utc).isoformat()
                }
            except Exception as e:
                health_status[symbol] = {
                    'status': 'offline',
                    'error': str(e),
                    'last_test': datetime.now(timezone.utc).isoformat()
                }

        # Overall health assessment
        online_count = sum(1 for s in health_status.values() if s['status'] == 'online')
        total_count = len(health_status)

        if online_count == total_count:
            overall_status = 'healthy'
        elif online_count >= total_count // 2:
            overall_status = 'degraded'
        else:
            overall_status = 'unhealthy'

        return jsonify({
            'health': {
                'overall_status': overall_status,
                'services': health_status,
                'online_services': online_count,
                'total_services': total_count,
                'uptime_percentage': round((online_count / total_count) * 100, 1)
            },
            'cache_info': {
                'cache_size': len(market_data.price_cache),
                'cache_expiry_count': len(market_data.cache_expiry)
            },
            'last_checked': datetime.now(timezone.utc).isoformat(),
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error checking market health: {e}")
        return jsonify({
            'health': {
                'overall_status': 'error',
                'error': str(e)
            },
            'success': False
        }), 500