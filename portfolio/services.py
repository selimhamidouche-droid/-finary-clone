import yfinance as yf
import ccxt
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from .models import Asset, AssetCategory
import logging

logger = logging.getLogger(__name__)

# Popular assets for market overview
MARKET_TICKERS = {
    'indices': [
        ('^GSPC', 'S&P 500'),
        ('^IXIC', 'NASDAQ'),
        ('^DJI', 'Dow Jones'),
        ('^FCHI', 'CAC 40'),
    ],
    'crypto': [
        ('BTC-USD', 'Bitcoin'),
        ('ETH-USD', 'Ethereum'),
        ('SOL-USD', 'Solana'),
        ('XRP-USD', 'XRP'),
    ],
    'stocks': [
        ('AAPL', 'Apple'),
        ('MSFT', 'Microsoft'),
        ('GOOGL', 'Google'),
        ('MC.PA', 'LVMH'),
        ('AI.PA', 'Air Liquide'),
        ('TTE.PA', 'TotalEnergies'),
    ],
}

def fetch_asset_details(ticker):
    """
    Fetches comprehensive details for a single asset from Yahoo Finance.
    Returns a dict with all available financial information.
    """
    cache_key = f'asset_detail_{ticker}'
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    try:
        t = yf.Ticker(ticker)
        info = t.info
        
        # Get historical data for chart
        hist = t.history(period='1mo')
        chart_data = []
        chart_labels = []
        if not hist.empty:
            for date, row in hist.iterrows():
                chart_labels.append(date.strftime('%d/%m'))
                price = row['Close']
                if hasattr(price, 'item'):
                    price = price.item()
                chart_data.append(round(price, 2))
        
        # Calculate 24h change
        hist_2d = t.history(period='2d')
        change_pct = 0
        if len(hist_2d) >= 2:
            current = hist_2d['Close'].iloc[-1]
            previous = hist_2d['Close'].iloc[-2]
            if hasattr(current, 'item'):
                current = current.item()
            if hasattr(previous, 'item'):
                previous = previous.item()
            if previous:
                change_pct = ((current - previous) / previous) * 100
        
        result = {
            'ticker': ticker,
            'name': info.get('shortName') or info.get('longName') or ticker,
            'price': info.get('regularMarketPrice') or info.get('currentPrice') or 0,
            'change_pct': round(change_pct, 2),
            'currency': info.get('currency', 'USD'),
            
            # Key metrics
            'market_cap': info.get('marketCap'),
            'volume': info.get('volume') or info.get('regularMarketVolume'),
            'avg_volume': info.get('averageVolume'),
            'pe_ratio': info.get('trailingPE'),
            'eps': info.get('trailingEps'),
            'dividend_yield': info.get('dividendYield'),
            'beta': info.get('beta'),
            
            # 52-week range
            'week_52_high': info.get('fiftyTwoWeekHigh'),
            'week_52_low': info.get('fiftyTwoWeekLow'),
            'day_high': info.get('dayHigh') or info.get('regularMarketDayHigh'),
            'day_low': info.get('dayLow') or info.get('regularMarketDayLow'),
            'open': info.get('open') or info.get('regularMarketOpen'),
            'previous_close': info.get('previousClose') or info.get('regularMarketPreviousClose'),
            
            # Company info
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'country': info.get('country'),
            'website': info.get('website'),
            'description': info.get('longBusinessSummary', '')[:500] if info.get('longBusinessSummary') else None,
            'employees': info.get('fullTimeEmployees'),
            
            # Chart data
            'chart_labels': chart_labels,
            'chart_data': chart_data,
            
            # Quote type
            'quote_type': info.get('quoteType', 'EQUITY'),
        }
        
        # Cache for 5 minutes
        cache.set(cache_key, result, 300)
        return result
        
    except Exception as e:
        logger.error(f"Error fetching details for {ticker}: {e}")
        # Return mock fallback data
        mock_data = {
            'AAPL': {'name': 'Apple Inc.', 'price': 185.92, 'change_pct': 0.67, 'market_cap': 2900000000000, 'pe_ratio': 30.5, 'sector': 'Technology'},
            'MSFT': {'name': 'Microsoft Corp.', 'price': 376.04, 'change_pct': 1.23, 'market_cap': 2800000000000, 'pe_ratio': 35.2, 'sector': 'Technology'},
            'GOOGL': {'name': 'Alphabet Inc.', 'price': 140.21, 'change_pct': -0.45, 'market_cap': 1800000000000, 'pe_ratio': 25.1, 'sector': 'Technology'},
            'BTC-USD': {'name': 'Bitcoin', 'price': 45721.00, 'change_pct': 2.41, 'market_cap': 900000000000, 'sector': 'Cryptocurrency'},
            'ETH-USD': {'name': 'Ethereum', 'price': 2430.50, 'change_pct': 1.15, 'market_cap': 290000000000, 'sector': 'Cryptocurrency'},
            'MC.PA': {'name': 'LVMH', 'price': 738.50, 'change_pct': 0.89, 'market_cap': 370000000000, 'pe_ratio': 24.5, 'sector': 'Consumer Goods'},
            '^GSPC': {'name': 'S&P 500', 'price': 4780.20, 'change_pct': 0.35, 'sector': 'Index'},
            '^FCHI': {'name': 'CAC 40', 'price': 7452.80, 'change_pct': 0.28, 'sector': 'Index'},
        }
        fallback = mock_data.get(ticker, {})
        return {
            'ticker': ticker,
            'name': fallback.get('name', ticker),
            'price': fallback.get('price', 0),
            'change_pct': fallback.get('change_pct', 0),
            'currency': 'USD',
            'market_cap': fallback.get('market_cap'),
            'pe_ratio': fallback.get('pe_ratio'),
            'sector': fallback.get('sector'),
            'chart_labels': ['01/01', '02/01', '03/01', '04/01', '05/01'],
            'chart_data': [100, 102, 101, 105, 103],
            'error': str(e),
        }

def fetch_market_data():
    """
    Fetches market data for popular indices, cryptos, and stocks.
    Returns dict with 'indices', 'crypto', 'stocks' keys.
    Results are cached for 5 minutes.
    Falls back to mock data if API fails.
    """
    cache_key = 'market_overview_data'
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    result = {'indices': [], 'crypto': [], 'stocks': []}
    api_success = False
    
    # Collect all tickers
    all_tickers = []
    for category, items in MARKET_TICKERS.items():
        for ticker, name in items:
            all_tickers.append(ticker)
    
    try:
        # Bulk fetch using yfinance
        data = yf.download(all_tickers, period='2d', group_by='ticker', progress=False)
        
        if not data.empty:
            for category, items in MARKET_TICKERS.items():
                for ticker, name in items:
                    try:
                        if len(all_tickers) == 1:
                            close_prices = data['Close']
                        else:
                            close_prices = data[ticker]['Close']
                        
                        if len(close_prices) >= 2:
                            current = close_prices.iloc[-1]
                            previous = close_prices.iloc[-2]
                            change_pct = ((current - previous) / previous) * 100 if previous else 0
                        else:
                            current = close_prices.iloc[-1] if len(close_prices) > 0 else 0
                            change_pct = 0
                        
                        # Convert numpy to Python
                        if hasattr(current, 'item'):
                            current = current.item()
                        if hasattr(change_pct, 'item'):
                            change_pct = change_pct.item()
                        
                        if current and current > 0:
                            api_success = True
                            result[category].append({
                                'ticker': ticker,
                                'name': name,
                                'price': round(current, 2),
                                'change_pct': round(change_pct, 2) if change_pct else 0,
                            })
                    except Exception as e:
                        logger.warning(f"Error fetching {ticker}: {e}")
    except Exception as e:
        logger.error(f"Error in fetch_market_data: {e}")
    
    # Fallback to mock data if API failed
    if not api_success:
        logger.info("Using mock market data as fallback")
        result = {
            'indices': [
                {'ticker': '^GSPC', 'name': 'S&P 500', 'price': 4780.20, 'change_pct': 0.35},
                {'ticker': '^IXIC', 'name': 'NASDAQ', 'price': 15032.50, 'change_pct': 0.52},
                {'ticker': '^DJI', 'name': 'Dow Jones', 'price': 37532.10, 'change_pct': -0.12},
                {'ticker': '^FCHI', 'name': 'CAC 40', 'price': 7452.80, 'change_pct': 0.28},
            ],
            'crypto': [
                {'ticker': 'BTC-USD', 'name': 'Bitcoin', 'price': 45721.00, 'change_pct': 2.41},
                {'ticker': 'ETH-USD', 'name': 'Ethereum', 'price': 2430.50, 'change_pct': 1.15},
                {'ticker': 'SOL-USD', 'name': 'Solana', 'price': 98.40, 'change_pct': 5.23},
                {'ticker': 'XRP-USD', 'name': 'XRP', 'price': 0.62, 'change_pct': -0.85},
            ],
            'stocks': [
                {'ticker': 'AAPL', 'name': 'Apple', 'price': 185.92, 'change_pct': 0.67},
                {'ticker': 'MSFT', 'name': 'Microsoft', 'price': 376.04, 'change_pct': 1.23},
                {'ticker': 'GOOGL', 'name': 'Google', 'price': 140.21, 'change_pct': -0.45},
                {'ticker': 'MC.PA', 'name': 'LVMH', 'price': 738.50, 'change_pct': 0.89},
                {'ticker': 'AI.PA', 'name': 'Air Liquide', 'price': 178.30, 'change_pct': 0.32},
                {'ticker': 'TTE.PA', 'name': 'TotalEnergies', 'price': 62.45, 'change_pct': -0.18},
            ],
        }
    
    # Cache for 5 minutes (or 1 minute for mock data)
    cache.set(cache_key, result, 300 if api_success else 60)
    return result

def update_asset_prices(assets):
    """
    Updates the current_price of the given list of Asset objects.
    """
    stocks = [a for a in assets if a.category == AssetCategory.STOCKS]
    cryptos = [a for a in assets if a.category == AssetCategory.CRYPTO]

    if stocks:
        _update_stocks(stocks)
    
    if cryptos:
        _update_cryptos(cryptos)

def _update_stocks(assets):
    tickers = [a.ticker for a in assets]
    if not tickers:
        return

    try:
        # yfinance allows bulk download
        # period='1d' is usually enough to get current price (Close or regularMarketPrice)
        # Using Tickers to get info is slower but more detailed. download is faster for bulk.
        # But download returns a DataFrame.
        # Let's use Tickers object for robustness or download for speed? 
        # For simplicity and robust current price:
        # yf.download(tickers, period="1d") returns OHLC data.
        
        # Alternative: fetch one by one if list is short, or bulk.
        # yfinance bulk is tricky if some tickers are invalid.
        
        # Let's try bulk download of 'Last Price'
        data = yf.download(tickers, period="1d", group_by='ticker', progress=False)
        
        # If single ticker, data structure is different.
        is_single = len(tickers) == 1
        
        for asset in assets:
            try:
                if is_single:
                     # Accessing the scalar value.
                     # 'Close' is the closing price. For live market, we might want 'Regular Market Price' 
                     # but Ticker.info is very slow. 'Close' from download is often previous close or current.
                     # Let's use the last available 'Close' price.
                     price = data['Close'].iloc[-1]
                else:
                    price = data[asset.ticker]['Close'].iloc[-1]
                
                # Handling NaN
                if hasattr(price, 'item'): 
                     price = price.item() # convert numpy float to python float
                
                if price and price > 0:
                    asset.current_price = Decimal(str(price))
                    asset.last_updated = timezone.now()
                    asset.save(update_fields=['current_price', 'last_updated'])
            except Exception as e:
                logger.error(f"Error updating stock {asset.ticker}: {e}")

    except Exception as e:
        logger.error(f"Error in stock bulk update: {e}")

def _update_cryptos(assets):
    # Instantiate exchange (e.g. Binance or CoinGecko via ccxt if available, or just generic)
    # efficient approach: use a public aggregator like binance for common pairs
    exchange = ccxt.binance() 
    
    # Note: CCXT fetch_tickers is efficient if supported
    try:
        # Get all needed tickers
        # CCXT symbols are often BTC/USDT. Asset.ticker should match this format.
        symbols = [a.ticker for a in assets]
        
        # fetchTickers might not be supported by all exchanges or for all symbols at once.
        # Binance supports it.
        try:
           ticker_data = exchange.fetch_tickers(symbols)
        except:
           # Fallback to one by one if bulk fails
           ticker_data = {}
           for sym in symbols:
               try:
                   ticker_data[sym] = exchange.fetch_ticker(sym)
               except Exception as e:
                   logger.error(f"Error fetching crypto {sym}: {e}")

        for asset in assets:
            if asset.ticker in ticker_data:
                data = ticker_data[asset.ticker]
                price = data.get('last') or data.get('close')
                if price:
                    asset.current_price = Decimal(str(price))
                    asset.last_updated = timezone.now()
                    asset.save(update_fields=['current_price', 'last_updated'])
    except Exception as e:
        logger.error(f"Error in crypto update: {e}")

def search_assets_online(query):
    """
    Search for assets using Yahoo Finance Autocomplete API.
    Returns a list of dicts: {'ticker':Str, 'name':Str, 'category': AssetCategory}
    """
    import requests
    
    results = []
    
    # Simple formatting of the query
    q = query.strip()
    if not q:
        return results
        
    # Yahoo Finance AutoComplete
    # We use a user-agent to avoid being blocked
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={q}"
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        
        for item in data.get('quotes', []):
            # We only care about EQUITY (Stocks), CRYPTOCURRENCY, ETFs, etc.
            quote_type = item.get('quoteType', '')
            symbol = item.get('symbol')
            shortname = item.get('shortname') or item.get('longname') or symbol
            
            category = None
            if quote_type == 'EQUITY':
                category = AssetCategory.STOCKS
            elif quote_type == 'CRYPTOCURRENCY':
                category = AssetCategory.CRYPTO
            elif quote_type == 'ETF':
                category = AssetCategory.STOCKS # Treat ETF as stocks for now
            elif quote_type == 'MUTUALFUND':
                category = AssetCategory.STOCKS
                
            if category and symbol:
                results.append({
                    'ticker': symbol,
                    'name': shortname,
                    'category': category,
                    'exists': Asset.objects.filter(ticker=symbol).exists()
                })
                
    except Exception as e:
        logger.error(f"Error searching Yahoo Finance for {query}: {e}")
        
    return results

def create_asset_from_ticker(ticker, category=None):
    """
    Fetches details for a ticker and creates it in DB.
    """
    import yfinance as yf
    
    try:
        t = yf.Ticker(ticker)
        # Fetch minimal history to get current price
        hist = t.history(period='1d')
        
        if hist.empty:
            return None
            
        price = hist['Close'].iloc[-1]
        
        # Try to infer name if we don't have it
        name = t.info.get('shortName') or t.info.get('longName') or ticker
        
        # Infer category if not provided
        if not category:
            qtype = t.info.get('quoteType')
            if qtype == 'CRYPTOCURRENCY':
                category = AssetCategory.CRYPTO
            else:
                category = AssetCategory.STOCKS
        
        # Convert numpy types to python Native types to avoid Decimal errors
        if hasattr(price, 'item'):
             price = price.item()
                
        asset, created = Asset.objects.update_or_create(
            ticker=ticker,
            defaults={
                'name': name,
                'category': category,
                'current_price': Decimal(str(price)),
                'last_updated': timezone.now()
            }
        )
        return asset
        
    except Exception as e:
        logger.error(f"Error creating asset {ticker}: {e}")
        return None

