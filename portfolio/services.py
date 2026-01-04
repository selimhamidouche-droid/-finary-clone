import yfinance as yf
import ccxt
from decimal import Decimal
from django.utils import timezone
from .models import Asset, AssetCategory
import logging

logger = logging.getLogger(__name__)

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

