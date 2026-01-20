"""
casa_price_scraper.py

Récupère le dernier prix de trading pour un ticker de la Bourse de Casablanca.

Principes:
- Utilise BeautifulSoup (requiert `requests` et `beautifulsoup4`).
- Tente plusieurs sources (liste de pages candidates) puis un fallback sur `yfinance` si disponible.
- Gestion d'erreurs et retries avec timeout raisonnable.
- Simple cache en mémoire pour éviter des requêtes trop fréquentes (paramètre `min_interval`).

Fonction publique:
    get_casablanca_price(ticker, timeout=5, retries=2, retry_delay=1.5, min_interval=2.0) -> float

Retourne un `float` ou lève `ValueError` en cas d'échec irrécoverable.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# In-memory simple cache to prevent excessive scraping frequency
_LAST_FETCH: dict[str, tuple[float, float]] = {}  # ticker -> (timestamp, price)


def _parse_number_string(s: str) -> Optional[float]:
    """Parse une chaîne contenant un nombre (avec ., ou ,) en float.

    Détecte séparateur décimal en regardant la position du dernier '.' ou ','.
    Gère milliers séparateurs.
    Retourne None si la chaîne ne semble pas représenter un nombre.
    """
    s = s.strip()
    if not s:
        return None

    # Keep only digits, dots and commas and optional leading -
    m = re.search(r"-?[\d.,]+", s)
    if not m:
        return None
    num = m.group(0)

    # If both separators present, decide which is decimal by last occurrence
    if ',' in num and '.' in num:
        if num.rfind(',') > num.rfind('.'):
            # comma is decimal sep
            num = num.replace('.', '')
            num = num.replace(',', '.')
        else:
            # dot is decimal sep
            num = num.replace(',', '')
    else:
        # Only one kind of separator or none: if comma present and no dot, treat comma as decimal
        if ',' in num and '.' not in num:
            num = num.replace(',', '.')
        else:
            # remove accidental spaces
            num = num

    try:
        return float(num)
    except ValueError:
        return None


def _scrape_url_for_price(url: str, ticker: str, timeout: float) -> Optional[float]:
    """Fetch a page and attempt to extract a last price for the given ticker."""
    headers = {
        'User-Agent': 'TradeSenseBot/1.0 (+https://example.com)'
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'lxml')

    # Heuristics: look for elements that commonly contain prices
    selectors = [
        'span.price',
        'div.price',
        'span.last',
        'div.last',
        "*[class*='price']",
        "*[id*='price']",
        "*[class*='cours']",
        "*[id*='cours']",
    ]

    text_candidates = []
    for sel in selectors:
        for el in soup.select(sel):
            if el and el.get_text(strip=True):
                text_candidates.append(el.get_text(strip=True))

    # Fallback: search for any numeric-looking token in the page near ticker occurrences
    if not text_candidates:
        # find occurrences of the ticker in the page and extract nearby text
        page_text = soup.get_text(' ', strip=True)
        # find positions where ticker appears
        for m in re.finditer(re.escape(ticker), page_text, flags=re.IGNORECASE):
            start = max(0, m.start() - 200)
            end = min(len(page_text), m.end() + 200)
            snippet = page_text[start:end]
            # collect numeric tokens in snippet
            nums = re.findall(r"-?[\d.,]+", snippet)
            text_candidates.extend(nums)

    # As ultimate fallback, search whole page for numbers
    if not text_candidates:
        page_text = soup.get_text(' ', strip=True)
        text_candidates = re.findall(r"-?[\d.,]+", page_text)

    # Try to parse candidates from most likely to least
    for token in text_candidates:
        price = _parse_number_string(token)
        if price is not None and price > 0:
            return price

    return None


def get_casablanca_price(
    ticker: str,
    timeout: float = 5.0,
    retries: int = 2,
    retry_delay: float = 1.5,
    min_interval: float = 2.0,
) -> float:
    """
    Retourne le dernier prix pour `ticker` (float).

    - Tente plusieurs sources; si l'une échoue, passe à la suivante.
    - Utilise un simple cache pour respecter `min_interval` entre requêtes pour le même ticker.
    - Lève `ValueError` en cas d'échec après tous les essais.
    """
    t = ticker.strip().upper()
    now = time.time()
    cached = _LAST_FETCH.get(t)
    if cached:
        ts, price = cached
        if now - ts < min_interval:
            logger.debug('Returning cached price for %s', t)
            return price

    # Candidate URLs to try (primary: Casablanca Bourse official site patterns)
    candidate_urls = [
        # Common public endpoints (may change) - try multiple patterns
        f'https://www.casablanca-bourse.com/bourseweb/en/Marche/Societe.aspx?code={t}',
        f'https://www.casablanca-bourse.com/bourseweb/fr/Marche/Societe.aspx?code={t}',
        f'https://www.casablanca-bourse.com/bourseweb/fr/General/Quote/Quote.aspx?Isin={t}',
        f'https://www.casablanca-bourse.com/bourseweb/en/General/Quote/Quote.aspx?Isin={t}',
    ]

    last_exception: Optional[Exception] = None

    for url in candidate_urls:
        attempt = 0
        while attempt <= retries:
            try:
                price = _scrape_url_for_price(url, t, timeout=timeout)
                if price is not None:
                    _LAST_FETCH[t] = (time.time(), price)
                    return price
                # If page returned but no price found, break to try next URL
                break
            except requests.exceptions.RequestException as rexc:
                logger.warning('Request error for %s: %s', url, rexc)
                last_exception = rexc
                attempt += 1
                time.sleep(retry_delay)
            except Exception as exc:
                logger.exception('Unexpected error scraping %s: %s', url, exc)
                last_exception = exc
                break

    # Fallback: try yfinance if available (may cover .MA tickers)
    try:
        import yfinance as yf

        logger.info('Falling back to yfinance for %s', t)
        # yfinance may use different symbol convention; try as-is and with .MA
        for candidate in (t, f'{t}.MA'):
            try:
                tk = yf.Ticker(candidate)
                hist = tk.history(period='1d', interval='1m')
                if hist is None or hist.empty:
                    hist = tk.history(period='5d')
                if hist is None or hist.empty:
                    continue
                closes = hist['Close'].dropna()
                if closes.empty:
                    continue
                price = float(closes.iloc[-1])
                _LAST_FETCH[t] = (time.time(), price)
                return price
            except Exception as yf_exc:
                logger.debug('yfinance candidate %s failed: %s', candidate, yf_exc)
                continue
    except Exception:
        logger.debug('yfinance not available or failed')

    # Nothing worked
    if last_exception:
        raise ValueError(f'Failed to fetch price for {ticker}: {last_exception}')
    raise ValueError(f'Price for {ticker} not found on Casablanca sources')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Fetch last price for Casablanca ticker')
    parser.add_argument('ticker', help='Ticker symbol (e.g., CIH)')
    parser.add_argument('--timeout', type=float, default=5.0)
    parser.add_argument('--retries', type=int, default=2)
    args = parser.parse_args()

    try:
        p = get_casablanca_price(args.ticker, timeout=args.timeout, retries=args.retries)
        print(float(p))
    except Exception as e:
        logger.error('Error: %s', e)
        raise
